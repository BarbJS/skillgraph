from src.session_store import SessionStore


def test_new_conversation_is_empty_and_selectable(tmp_path):
    store = SessionStore(tmp_path / "state.sqlite")
    first = store.create_conversation("Primeira", "crewai", role="RH")
    second = store.create_conversation("Nova conversa", "crewai", role="RH")
    assert first != second
    assert store.messages(second, role="RH") == []
    assert {item["id"] for item in store.list_conversations(role="RH")} == {first, second}


def test_conversation_history_persists_user_and_assistant_messages(tmp_path):
    store = SessionStore(tmp_path / "state.sqlite")
    conversation = store.create_conversation("ML", "crewai", role="desenvolvedor")
    store.add_message(conversation, "user", "Qual trilha priorizar?", route="ml_prediction", conversation_role="desenvolvedor")
    store.add_message(conversation, "assistant", "Trilha de dados.", route="ml_prediction", conversation_role="desenvolvedor")
    history = store.messages(conversation, role="desenvolvedor")
    assert [item["role"] for item in history] == ["user", "assistant"]
    assert history[1]["content"] == "Trilha de dados."


def test_conversation_history_is_isolated_by_role(tmp_path):
    store = SessionStore(tmp_path / "state.sqlite")
    developer = store.create_conversation("Dev", role="desenvolvedor")
    rh = store.create_conversation("RH", role="RH")
    store.add_message(developer, "user", "dev", conversation_role="desenvolvedor")
    store.add_message(rh, "user", "rh", conversation_role="RH")
    assert len(store.list_conversations(role="desenvolvedor")) == 1
    assert len(store.list_conversations(role="RH")) == 1
    assert store.messages(developer, role="RH") == []


def test_conversations_can_be_isolated_by_backend(tmp_path):
    store = SessionStore(tmp_path / "state.sqlite")
    chat = store.create_conversation("Chat", backend="crewai", role="desenvolvedor")
    ml = store.create_conversation("ML", backend="ml", role="desenvolvedor")
    assert store.list_conversations(role="desenvolvedor", backend="crewai")[0]["id"] == chat
    assert store.list_conversations(role="desenvolvedor", backend="ml")[0]["id"] == ml
    assert store.get_conversation(chat, role="desenvolvedor", backend="ml") is None
    assert store.get_conversation(ml, role="desenvolvedor", backend="ml")["title"] == "ML"
