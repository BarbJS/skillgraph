from src.reasoning import (
    PublicReasoningStep,
    core_decision_step,
    route_steps,
    sanitize_steps,
    step,
)


def test_core_decision_is_public_and_sanitized():
    value = core_decision_step(
        {
            "intent": "resume_analysis",
            "next_agent": "Resume Interpreter",
            "reason": "Há um PDF",
            "validation": "PII será removida",
        }
    )
    assert value["stage"] == "Core Router"
    assert "Resume Interpreter" in value["summary"]


def test_private_reasoning_fields_are_discarded():
    assert (
        sanitize_steps(
            [
                {
                    "stage": "x",
                    "status": "completed",
                    "summary": "ok",
                    "thought": "secret",
                }
            ]
        )
        == []
    )


def test_reasoning_steps_are_persistable():
    assert (
        sanitize_steps([step("Core Router", "Rota validada")])[0]["stage"]
        == "Core Router"
    )


def test_public_reasoning_contains_no_private_thought_field():
    value = step("Roteamento", "Fluxo selecionado")
    assert set(value) == {"stage", "status", "summary", "tool"}
    assert "thought" not in value
    assert PublicReasoningStep.model_validate(value)


def test_route_steps_are_safe_public_summaries():
    steps = route_steps("rag")
    assert steps
    assert all("summary" in item for item in steps)
    assert all("chain" not in item["summary"].lower() for item in steps)
