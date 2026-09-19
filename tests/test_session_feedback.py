from pathlib import Path

from src.feedback import FeedbackStore
from src.session_store import SessionStore


def test_session_store_persists_and_searches(tmp_path):
    store = SessionStore(tmp_path / "state.sqlite")
    conversation = store.create_conversation("Pergunta inicial")
    message_id = store.add_message(conversation, "user", "Quais competências têm mais lacunas?", route="sql_indicator")
    store.add_message(conversation, "assistant", "Resultado", route="sql_indicator")
    assert store.messages(conversation)[0]["id"] == message_id
    assert store.search_conversations("lacunas")[0]["id"] == conversation
    store.rename_conversation(conversation, "Indicadores de lacunas")
    assert store.get_conversation(conversation)["title"] == "Indicadores de lacunas"


def test_feedback_store_saves_optional_comment(tmp_path):
    feedback = FeedbackStore(tmp_path / "feedback.sqlite")
    feedback.save("m1", -1, route="rag", comment="Resposta incompleta")
    assert feedback.get("m1")["comment"] == "Resposta incompleta"
    assert feedback.summary()["negative"] == 1
