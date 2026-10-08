"""Safe, user-facing technical error diagnostics."""

from __future__ import annotations

import re
from typing import Any

_SECRET = re.compile(
    r"(?i)(bearer\s+\S+|sk-[A-Za-z0-9_-]+|xoxb-[A-Za-z0-9_-]+|TYPESAFE_API_KEY\s*[:=]\s*\S+)"
)


def sanitize_detail(value: Any, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    text = _SECRET.sub("[REDACTED]", text)
    text = re.sub(
        r"(?i)(cpf|rg|e-?mail|telefone|endereço)\s*[:=]?\s*\S+", r"\1 [REDACTED]", text
    )
    return text[:limit]


def classify_error(error: Any) -> tuple[str, str, str]:
    """Return stable category, public message and suggested action."""
    text = sanitize_detail(error).casefold()
    if "jev" in text or "systemone" in text or "tls" in text or "certificat" in text:
        return (
            "JEV/TLS",
            "A análise estruturada do currículo não foi concluída.",
            "Verifique a conexão segura e a disponibilidade do serviço de análise.",
        )
    if "ocr" in text or "pdf" in text or "extract" in text:
        return (
            "OCR/PDF",
            "Não foi possível extrair o conteúdo do currículo.",
            "Confirme que o PDF está legível e tente novamente.",
        )
    if "dify" in text or "chatflow" in text:
        return (
            "Dify/RAG",
            "O serviço documental não respondeu.",
            "Verifique se o Dify está ativo e tente novamente.",
        )
    if "duckdb" in text or "sql" in text:
        return (
            "Dados estruturados",
            "A consulta aos dados estruturados falhou.",
            "Tente reformular a pergunta ou contate o suporte.",
        )
    if "llm" in text or "none or empty" in text or "modelo" in text:
        return (
            "Modelo de linguagem",
            "O modelo não retornou uma resposta válida.",
            "Verifique o modelo local e tente novamente.",
        )
    if "timeout" in text or "timed out" in text:
        return (
            "Tempo limite",
            "A análise excedeu o tempo esperado.",
            "Aguarde alguns instantes e tente novamente.",
        )
    return (
        "Fluxo especialista",
        "O fluxo de análise não foi concluído.",
        "Tente novamente; se persistir, envie o ID técnico ao suporte.",
    )


def technical_payload(
    *, trace_id: str, route: str, elapsed_seconds: float, error: Any, developer: bool
) -> dict[str, str]:
    category, message, action = classify_error(error)
    payload = {
        "Categoria": category,
        "Rota": route,
        "Trace ID": trace_id,
        "Tempo decorrido": f"{elapsed_seconds:.1f}s",
        "Próxima ação": action,
    }
    if developer:
        payload["Detalhe sanitizado"] = sanitize_detail(error)
    return payload


def render_error_panel(
    *, trace_id: str, route: str, started: float, error: Any, developer: bool = False
) -> None:
    import streamlit as st
    from time import perf_counter

    category, message, action = classify_error(error)
    st.error(message)
    with st.expander("Detalhes técnicos (seguro)", expanded=developer):
        payload = technical_payload(
            trace_id=trace_id,
            route=route,
            elapsed_seconds=perf_counter() - started,
            error=error,
            developer=developer,
        )
        st.json(payload)
        if not developer:
            st.caption(
                "Envie o Trace ID ao suporte; detalhes internos não são exibidos neste perfil."
            )


def safe_public_error(error: Any) -> str:
    return classify_error(error)[1]
