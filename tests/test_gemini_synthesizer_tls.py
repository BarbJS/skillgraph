import requests

from src.gemini_synthesizer import GeminiSynthesisError, GeminiSynthesizer


class TlsSession:
    def post(self, *args, **kwargs):
        raise requests.exceptions.SSLError("certificate verify failed")


def test_gemini_tls_failure_has_actionable_message():
    client = GeminiSynthesizer(enabled=True, api_key="key", session=TlsSession())
    try:
        client.synthesize({"draft_answer": "safe"})
    except GeminiSynthesisError as exc:
        assert "TLS" in str(exc)
    else:
        raise AssertionError("TLS failure should be surfaced")
