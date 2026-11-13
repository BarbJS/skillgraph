from src.output_security import validate_user_output


def test_ml_recommendation_with_governance_language_is_allowed():
    response = (
        "A trilha recomendada é Dados e Ciência de Dados. "
        "Esta é uma recomendação de desenvolvimento, não uma decisão de promoção, "
        "remuneração ou desligamento."
    )
    assert validate_user_output(response, route="ml_prediction") == response
