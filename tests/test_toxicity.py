from src.toxicity import safe_response


def test_toxic_response_is_replaced():
    response, result = safe_response("Você é um idiota")
    assert result.passed is False
    assert "ajudar" in response


def test_professional_response_passes():
    response, result = safe_response("Posso ajudar com trilhas de desenvolvimento.")
    assert result.passed is True
    assert response.startswith("Posso")
