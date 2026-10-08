"""DeepEval model adapter for OpenAI-compatible LM Studio."""

from __future__ import annotations

import os
from typing import Any

try:
    from deepeval.models import DeepEvalBaseLLM
except ImportError:

    class DeepEvalBaseLLM:
        pass


class LocalDeepEvalModel(DeepEvalBaseLLM):
    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model_name = model or os.getenv(
            "EVAL_JUDGE_MODEL", "meta-llama-3-8b-instruct"
        )
        self.base_url = base_url or os.getenv(
            "EVAL_JUDGE_BASE_URL", "http://127.0.0.1:1234/v1"
        )
        self.api_key = api_key or os.getenv("EVAL_JUDGE_API_KEY", "lm-studio-local")
        super().__init__(model_name=self.model_name)

    def load_model(self, *args, **kwargs) -> "LocalDeepEvalModel":
        return self

    def generate(self, prompt: str, schema: Any | None = None) -> Any:
        from openai import OpenAI

        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        kwargs = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 800,
        }
        if schema is not None and hasattr(schema, "model_json_schema"):
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "deepeval_output",
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            }
        response = client.chat.completions.create(**kwargs)
        content = str(response.choices[0].message.content)
        if schema is not None and hasattr(schema, "model_validate"):
            import json

            try:
                return schema.model_validate(json.loads(content))
            except Exception:
                pass
        return content

    async def a_generate(self, prompt: str, schema: Any | None = None) -> Any:
        return self.generate(prompt, schema)

    def get_model_name(self) -> str:
        return self.model_name

    def get_model(self) -> "LocalDeepEvalModel":
        return self
