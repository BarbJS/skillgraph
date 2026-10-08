"""User-facing privacy guidance for document uploads."""

from __future__ import annotations

UPLOAD_PRIVACY_NOTICE = (
    "**Privacidade no upload:** não envie CPF, RG, endereço, telefone, e-mail pessoal, "
    "salário ou outros identificadores desnecessários. Use uma descrição não identificadora "
    "quando possível. O PDF é processado temporariamente para extração/OCR e análise; "
    "a análise pode levar até 5 minutos. Os guardrails continuam ativos mesmo assim."
)


def upload_privacy_notice() -> str:
    return UPLOAD_PRIVACY_NOTICE
