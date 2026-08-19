"""Robust-ish JSON extraction from LLM text output (handles markdown fences)."""
from __future__ import annotations

import json
import re


class LLMJsonParseError(Exception):
    pass


def extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMJsonParseError(f"No JSON object found in LLM output: {text[:300]!r}")

    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMJsonParseError(f"Failed to parse JSON from LLM output: {exc}\nRaw: {text[:500]!r}") from exc
