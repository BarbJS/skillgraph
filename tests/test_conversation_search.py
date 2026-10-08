from src.session_store import SessionStore


def test_search_conversations_matches_title_and_content(tmp_path):
    store = SessionStore(tmp_path / "state.sqlite")
    first = store.create_conversation("Análise de currículo", role="RH")
    store.add_message(
        first, "user", "Analise Python e segurança", conversation_role="RH"
    )
    second = store.create_conversation("Políticas", role="RH")
    store.add_message(
        second, "user", "Qual o prazo de reembolso?", conversation_role="RH"
    )

    assert [
        item["id"] for item in store.search_conversations("currículo", role="RH")
    ] == [first]
    assert [
        item["id"] for item in store.search_conversations("reembolso", role="RH")
    ] == [second]


def test_search_conversations_isolates_roles(tmp_path):
    store = SessionStore(tmp_path / "state.sqlite")
    developer = store.create_conversation("Diagnóstico técnico", role="desenvolvedor")
    store.add_message(
        developer, "user", "observabilidade", conversation_role="desenvolvedor"
    )
    manager = store.create_conversation("Visão do gestor", role="gestor")
    store.add_message(manager, "user", "observabilidade", conversation_role="gestor")

    results = store.search_conversations("observabilidade", role="gestor")
    assert [item["id"] for item in results] == [manager]
