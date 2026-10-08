"""Structured resume-to-profile extraction and deterministic rendering."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from src.agents.schemas import EmployeeProfile, SkillEvidence
from src.privacy import redact_text

_PROFILE_PROMPT = """Você extrai competências de um currículo sanitizado.
Retorne SOMENTE JSON válido neste formato:
{"employee_context":"colaborador não identificado","skills":[{"name":"Python","normalized_name":"Programming","level":4,"confidence":0.8,"evidence":"frase curta do currículo"}],"unrecognized_skills":[{"name":"...","level":null,"confidence":0.3,"evidence":"..."}],"missing_information":["..."]}

Regras:
- Liste TODAS as competências e habilidades explicitamente mencionadas no currículo, não só as perguntadas por outra API.
- level é 0 a 5 somente quando houver evidência; use null quando não for determinável.
- Não transforme ausência de informação em nível 0.
- Para nível incerto, mantenha a competência na lista com confidence baixa e evidência curta.
- Não invente nome, cargo, nível, competência ou evidência.
- Não inclua PII.
"""


def _json_object(raw: str) -> dict[str, Any]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise ValueError("O extrator de currículo não retornou JSON válido.")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("O extrator de currículo retornou um formato inválido.")
    return value


def extract_profile(resume_text: str, jev_result: dict[str, Any]) -> EmployeeProfile:
    """Extract and validate all explicit skills through the local LLM."""
    redacted, _ = redact_text(resume_text)
    host = os.getenv("LM_STUDIO_HOST", "127.0.0.1")
    port = os.getenv("LM_STUDIO_PORT", "1234")
    base_url = os.getenv("RESUME_PROFILE_BASE_URL", f"http://{host}:{port}/v1").rstrip(
        "/"
    )
    model = os.getenv(
        "RESUME_PROFILE_MODEL",
        os.getenv("LM_STUDIO_CHAT_MODEL", "meta-llama-3-8b-instruct"),
    )
    api_key = os.getenv(
        "RESUME_PROFILE_API_KEY", os.getenv("LM_STUDIO_API_KEY", "lm-studio-local")
    )
    prompt = f"Currículo sanitizado:\n{redacted[:16000]}\n\nSinais estruturados do JEV (complementares):\n{json.dumps(jev_result, ensure_ascii=False)}"
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": _PROFILE_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 1800,
            "response_format": {"type": "json_object"},
        },
        timeout=(5, 120),
    )
    if response.status_code == 400:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _PROFILE_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 1800,
            },
            timeout=(5, 120),
        )
    response.raise_for_status()
    body = response.json()
    raw = body["choices"][0]["message"]["content"]
    value = _json_object(str(raw))
    value["source"] = "uploaded_resume"
    value["contains_pii"] = False
    return EmployeeProfile.model_validate(value)


def _format_skill(skill: SkillEvidence) -> str:
    level = f"{skill.level:g}/5" if skill.level is not None else "não determinável"
    confidence = (
        f"{skill.confidence:.2f}"
        if skill.confidence is not None
        else "baixa/não informada"
    )
    evidence = skill.evidence or "evidência insuficiente no currículo"
    return f"- **{skill.name}** — nível {level}; confiança {confidence}; evidência: {evidence}"


def render_profile(profile: EmployeeProfile) -> str:
    """Render every skill without allowing the synthesizer to omit entries."""
    recognized = (
        "\n".join(_format_skill(item) for item in profile.skills)
        or "- Nenhuma competência com evidência suficiente."
    )
    unknown = (
        "\n".join(_format_skill(item) for item in profile.unrecognized_skills)
        or "- Nenhuma."
    )
    missing = (
        "\n".join(f"- {item}" for item in profile.missing_information) or "- Nenhuma."
    )
    return (
        "**Competências e habilidades identificadas**\n\n"
        f"{recognized}\n\n"
        "**Competências mencionadas, mas não reconhecidas ou com nível incerto**\n\n"
        f"{unknown}\n\n"
        "**Informações ausentes ou que exigem confirmação**\n\n"
        f"{missing}\n\n"
        "A análise é um apoio ao desenvolvimento e requer revisão humana."
    )
