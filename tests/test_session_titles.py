from pathlib import Path

from app import _title_from_question


def test_conversation_title_is_topic_label():
    assert _title_from_question("Qual é a carga horária de um cargo sênior comparado com um júnior?") == "Comparação de carga horária entre cargos"
    assert _title_from_question("Quais competências têm mais lacunas?") == "Indicadores de lacunas de competências"
    assert _title_from_question("Quais treinamentos estão disponíveis?") == "Catálogo e recomendações de treinamentos"
