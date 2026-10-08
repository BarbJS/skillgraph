from app import _title_for_route, _title_from_question


def test_conversation_title_is_topic_label():
    assert (
        _title_from_question(
            "Qual é a carga horária de um cargo sênior comparado com um júnior?"
        )
        == "Comparação de carga horária entre cargos"
    )
    assert (
        _title_from_question("Quais competências têm mais lacunas?")
        == "Indicadores de lacunas de competências"
    )
    assert (
        _title_from_question("Quais treinamentos estão disponíveis?")
        == "Catálogo e recomendações de treinamentos"
    )


def test_route_titles_are_specific():
    assert _title_for_route("resume_analysis") == "Análise de currículo"
    assert (
        _title_for_route("ml_prediction") == "Recomendação de trilhas de competências"
    )
    assert _title_for_route("policy_rag") == "Políticas de treinamento"
    assert _title_for_route("structured_data") == "Consulta de dados estruturados"


def test_fallback_title_remains_topic_based():
    assert (
        _title_for_route("clarify", "qual assunto devo perguntar?")
        == "Consulta sobre desenvolvimento profissional"
    )
