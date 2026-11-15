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

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _provider() -> str:
    return os.getenv(
        "RESUME_PROFILE_PROVIDER",
        os.getenv("ML_INTERPRETER_PROVIDER", "openai_compatible"),
    ).strip().casefold()


def _gemini_model() -> str:
    model = os.getenv(
        "RESUME_PROFILE_MODEL",
        os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
    ).strip()
    return model.removeprefix("gemini/")


def _gemini_profile_request(prompt: str) -> str:
    api_key = os.getenv(
        "RESUME_PROFILE_API_KEY", os.getenv("GEMINI_API_KEY", "")
    ).strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não configurada para a extração do perfil do currículo."
        )
    base_url = os.getenv("RESUME_PROFILE_BASE_URL", _GEMINI_BASE_URL).rstrip("/")
    response = requests.post(
        f"{base_url}/models/{_gemini_model()}:generateContent",
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": _PROFILE_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 1800,
                "responseMimeType": "application/json",
            },
        },
        timeout=(5, 120),
    )
    try:
        response.raise_for_status()
        body = response.json()
        parts = body["candidates"][0]["content"]["parts"]
        return "".join(
            str(part.get("text", "")) for part in parts if isinstance(part, dict)
        )
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "O Gemini não conseguiu estruturar o perfil do currículo."
        ) from exc


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
    """Extract and validate all explicit skills through the configured provider."""
    redacted, _ = redact_text(resume_text)
    host = os.getenv("LM_STUDIO_HOST", "127.0.0.1")
    port = os.getenv("LM_STUDIO_PORT", "1234")
    base_url = os.getenv("RESUME_PROFILE_BASE_URL", f"http://{host}:{port}/v1").rstrip(
        "/"
    )
    model = os.getenv(
        "RESUME_PROFILE_MODEL",
        os.getenv("LM_STUDIO_CHAT_MODEL", "gemini-3.1-flash-lite"),
    )
    api_key = os.getenv(
        "RESUME_PROFILE_API_KEY", os.getenv("LM_STUDIO_API_KEY", "lm-studio-local")
    )
    prompt = (
        f"Currículo sanitizado:\n{redacted[:16000]}\n\n"
        "Sinais estruturados do JEV (complementares):\n"
        f"{json.dumps(jev_result, ensure_ascii=False)}"
    )
    if _provider() == "gemini":
        raw = _gemini_profile_request(prompt)
    else:
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
