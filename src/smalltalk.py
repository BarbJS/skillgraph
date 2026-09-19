"""Safe, lightweight social conversation responses."""

from __future__ import annotations


def smalltalk_answer(question: str) -> str:
    normalized = " ".join(question.lower().split())
    if any(greeting in normalized for greeting in ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite")):
        return (
            "Olá! Eu sou o SkillGraph, assistente da NexaTech para competências e aprendizagem corporativa. "
            "Posso ajudar com políticas de treinamento, requisitos de cargos, trilhas e indicadores estruturados."
        )
    if any(word in normalized for word in ("obrigado", "obrigada", "valeu")):
        return "De nada! Quando quiser, posso ajudar a consultar políticas, cargos, trilhas ou indicadores da NexaTech."
    if any(word in normalized for word in ("tudo bem", "como você está", "como voce esta")):
        return "Tudo bem por aqui! Estou pronto para ajudar com desenvolvimento profissional e aprendizagem corporativa."
    if any(word in normalized for word in ("tchau", "até mais", "ate mais")):
        return "Até mais! Volte quando quiser continuar a conversa sobre desenvolvimento profissional."
    return "Posso ajudar com políticas, cargos, competências, trilhas de desenvolvimento e indicadores da NexaTech."
