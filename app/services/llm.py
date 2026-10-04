import json
import logging
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class OpenAICompatibleLLM:
    """Small provider-neutral client for OpenAI-compatible chat completion APIs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.llm_api_key)

    async def structured_completion(self, *, system: str, prompt: str, output_model: type[T]) -> T:
        if not self.settings.llm_api_key:
            raise LLMError("LLM is not configured")
        endpoint = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            return output_model.model_validate(json.loads(raw))
        except (
            httpx.HTTPError,
            KeyError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            logger.warning("LLM request or validation failed: %s", type(exc).__name__)
            raise LLMError("LLM generation failed validation") from exc
