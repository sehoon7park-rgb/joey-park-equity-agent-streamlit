from __future__ import annotations

import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from joey_park.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None, model: str):
        self._api_key = api_key
        self._model = model
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else None

    def is_configured(self) -> bool:
        return self._client is not None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def complete(self, *, system: str, prompt: str, max_tokens: int = 2000) -> LLMResponse:
        if not self._client:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured. Set it in .env before calling any LLM-backed agent "
                "(Research/Critic/Decision)."
            )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        if response.stop_reason == "max_tokens":
            logger.warning(
                "Anthropic response truncated at max_tokens=%d (model=%s) — output is likely invalid/incomplete JSON.",
                max_tokens, self._model,
            )
        return LLMResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self._model,
            stop_reason=response.stop_reason,
        )
