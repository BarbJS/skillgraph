"""Natural-language orchestration for collaborator competency recommendations."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.ml_pipeline import load_artifact, normalize_skill_name, recommend_from_profile


INTERPRETER_PROMPT = """Você é o interpretador da área de desenvolvimento de colaboradores do SkillGraph.
O analista ou gestor de RH está descrevendo UM COLABORADOR, não o próprio usuário.
A tarefa é recomendar trilhas técnicas e competências prioritárias para desenvolvimento.
Não avalie contratação, promoção, remuneração, punição ou desligamento.
Não peça CPF, nome, e-mail ou qualquer identificador pessoal. Use apenas um rótulo não identificador como 'colaborador da equipe de dados'.
Sua saída deve ser somente JSON válido:
{"action":"recommend_track","employee_context":"...","skills":{"nome da competência":0-5},"goal":"..."}
Os níveis significam: 0 desconhecida, 1 inicial, 2 básico, 3 intermediário, 4 avançado, 5 especialista.
Extraia somente competências explicitamente informadas. Normalize nomes comuns (Python, SQL, análise de dados, Machine Learning, IA generativa, cloud, segurança, comunicação).
Se a pergunta não pedir recomendação para um colaborador, use:
{"action":"clarify","question":"Descreva as competências de um colaborador e peça uma trilha ou prioridade de desenvolvimento."}
Se não houver nenhuma competência, peça que o analista informe pelo menos uma competência observada. Não invente níveis.
"""

EXPLAINER_PROMPT = """Você é o assistente de desenvolvimento profissional do SkillGraph.
Explique o resultado estruturado recebido pelo backend para o colaborador descrito pelo analista/gestor de RH.
Responda em português do Brasil, sem jargão técnico de Machine Learning.
Apresente as até três trilhas mais compatíveis, as competências reconhecidas e as prioridades de desenvolvimento.
Deixe claro que é uma recomendação de apoio a uma conversa de desenvolvimento baseada em referências O*NET, não uma avaliação definitiva nem uma decisão de RH.
Não invente competências, causalidade ou dados pessoais. Não recomende contratação, promoção, remuneração, punição ou desligamento.
"""


class MLAssistantError(RuntimeError):
    pass


@dataclass(frozen=True)
class MLAssistantResult:
    answer: str
    recommendations: list[dict[str, Any]] | None = None
    priorities: list[dict[str, Any]] | None = None
    profile: dict[str, Any] | None = None
    structured: dict[str, Any] | None = None
    raw_action: str = "recommend_track"


def _json_object(raw: str) -> dict[str, Any]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise MLAssistantError("O interpretador não retornou JSON válido.") from exc
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as nested:
            raise MLAssistantError("O interpretador retornou JSON inválido.") from nested
    if not isinstance(value, dict):
        raise MLAssistantError("O interpretador retornou um objeto inesperado.")
    return value


def _coerce_profile(value: dict[str, Any]) -> dict[str, Any]:
    skills = value.get("skills")
    if not isinstance(skills, dict) or not skills:
        raise MLAssistantError("Informe pelo menos uma competência observada no colaborador.")
    clean: dict[str, float] = {}
    for name, level in skills.items():
        if not str(name).strip():
            continue
        try:
            numeric = float(level)
        except (TypeError, ValueError) as exc:
            raise MLAssistantError(f"O nível informado para {name} precisa ser de 0 a 5.") from exc
        if not 0 <= numeric <= 5:
            raise MLAssistantError(f"O nível informado para {name} precisa estar entre 0 e 5.")
        clean[normalize_skill_name(str(name))] = numeric
    if not clean:
        raise MLAssistantError("Informe pelo menos uma competência observada no colaborador.")
    context = str(value.get("employee_context") or "colaborador não identificado").strip()
    if any(token in context.casefold() for token in ("cpf", "email", "e-mail", "telefone", "nome completo")):
        raise MLAssistantError("Use apenas um rótulo não identificador para o colaborador.")
    return {"employee_context": context, "skills": clean, "goal": str(value.get("goal") or "desenvolvimento profissional").strip()}


class LocalMLAssistant:
    """Use LM Studio for language, while the backend owns model execution."""

    def __init__(self, artifact_path: Path, *, base_url: str | None = None, model: str | None = None, api_key: str | None = None, session: requests.Session | None = None) -> None:
        host = os.getenv("LM_STUDIO_HOST", "127.0.0.1")
        port = os.getenv("LM_STUDIO_PORT", "1234")
        self.base_url = (base_url or f"http://{host}:{port}/v1").rstrip("/")
        self.model = model or os.getenv("LM_STUDIO_CHAT_MODEL", "meta-llama-3-8b-instruct")
        self.api_key = api_key or os.getenv("LM_STUDIO_API_KEY", "lm-studio-local")
        self.artifact_path = artifact_path
        self.session = session or requests.Session()

    def _completion(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": 600}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = self.session.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload, timeout=(5, 60))
            if json_mode and response.status_code == 400:
                return self._completion(messages, False)
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"])
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise MLAssistantError("Não foi possível consultar o modelo local.") from exc

    def predict_from_question(self, question: str) -> MLAssistantResult:
        if not question.strip():
            raise MLAssistantError("Descreva as competências de um colaborador.")
        interpretation = _json_object(self._completion([{"role": "system", "content": INTERPRETER_PROMPT}, {"role": "user", "content": question}], True))
        if interpretation.get("action") == "clarify":
            return MLAssistantResult(str(interpretation.get("question") or "Descreva as competências do colaborador."), raw_action="clarify")
        if interpretation.get("action") != "recommend_track":
            raise MLAssistantError("A ação solicitada não é permitida nesta área.")
        profile = _coerce_profile(interpretation)
        try:
            load_artifact(self.artifact_path)
            structured = recommend_from_profile(self.artifact_path, profile["skills"])
        except (FileNotFoundError, ValueError, OSError, KeyError) as exc:
            raise MLAssistantError("O modelo de competências não está disponível. O administrador deve preparar o artefato O*NET.") from exc
        context = json.dumps({"employee_context": profile["employee_context"], "goal": profile["goal"], **structured}, ensure_ascii=False)
        try:
            answer = self._completion([{"role": "system", "content": EXPLAINER_PROMPT}, {"role": "user", "content": f"Resultado calculado pelo backend:\n{context}"}])
        except MLAssistantError:
            tracks = ", ".join(item["track"] for item in structured["recommendations"])
            answer = f"Trilhas mais compatíveis para o colaborador: {tracks}. As prioridades devem ser validadas em uma conversa de desenvolvimento."
        if structured.get("unrecognized_skills"):
            answer += "\n\nAlgumas competências informadas não foram encontradas no vocabulário atual e não influenciaram esta recomendação: " + ", ".join(item["input"] for item in structured["unrecognized_skills"]) + "."
        if structured.get("uncertainty", {}).get("needs_more_information"):
            answer += "\n\nA recomendação tem incerteza maior; informe outras competências para aumentar a confiança."
        return MLAssistantResult(answer.strip(), structured["recommendations"], structured["priorities"], profile, structured)
