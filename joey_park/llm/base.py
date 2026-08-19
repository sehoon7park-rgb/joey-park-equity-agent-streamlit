"""Provider-agnostic LLM interface (master-spec section 27).

Only an Anthropic implementation ships in the MVP (the user confirmed an
Anthropic key), but every agent depends on this interface, not on the
Anthropic SDK directly, so a second provider is a new file, not a rewrite.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str | None = None  # "max_tokens" means the response was cut off mid-output


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, *, system: str, prompt: str, max_tokens: int = 2000) -> LLMResponse:
        """Single-turn completion. Raises on failure — callers must catch and
        degrade (e.g. mark the narrative DATA_NOT_AVAILABLE), never invent a
        response on error.
        """
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError
