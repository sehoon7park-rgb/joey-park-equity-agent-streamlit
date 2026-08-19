"""Research Agent — the first of three LLM calls in the pipeline.

Turns pre-computed, sourced facts into a business narrative. Per
docs/DECISION_LOG.md D4, this agent is FORBIDDEN from introducing any
number not present in the facts it's given; the system prompt enforces this
and the Critic Agent checks it afterward.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from joey_park.llm.base import LLMProvider
from joey_park.llm.json_utils import LLMJsonParseError, extract_json

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the Research Agent inside the Joey Park U.S. Equity Investment Agent.

You will be given a JSON object of pre-computed, sourced facts about one U.S.-listed company.
Your job is to write a grounded business narrative from ONLY those facts.

HARD RULES:
- Never state a number that is not present in the provided facts. If a number would be useful
  but is not present, write "DATA_NOT_AVAILABLE" for that point instead of estimating it.
- Every claim must be traceable to a specific field in the provided facts. Do not use outside
  knowledge of the company to fill gaps.
- If the facts are too sparse to answer a section meaningfully, say so plainly rather than
  padding with generic language.
- Do not give an investment recommendation here — that is a separate agent's job. Stay descriptive.

LANGUAGE: Write every narrative/text VALUE in the JSON (business_summary, quality_notes,
competitive_position, catalysts[].description, catalysts[].grounded_in, data_gaps entries) in
natural, professional Korean (한국어), as if for a Korean-speaking investor. JSON KEYS stay in
English exactly as shown below — do not translate or rename them. The single exception is the
literal sentinel "DATA_NOT_AVAILABLE": if an entire field cannot be determined from the facts at
all, output that exact English token unchanged (so the app can detect it programmatically) —
but when you're only noting a partial gap inside otherwise-Korean prose, just say so in Korean
instead of inserting the English token mid-sentence.

Respond with ONLY a JSON object, no prose outside it, matching this shape:
{
  "business_summary": "무엇으로 돈을 버는 회사인지, 제공된 사실에 근거해서 한국어로",
  "growth_drivers": ["성장 동력 1 (한국어)", "성장 동력 2 (한국어)"],
  "quality_notes": "마진/수익률/재무건전성에 대한 한국어 평가",
  "competitive_position": "구조적/경쟁적 위치에 대한 한국어 설명, 근거 부족 시 DATA_NOT_AVAILABLE",
  "catalysts": [{"description": "한국어 설명", "grounded_in": "근거가 된 사실/공시 (한국어)"}],
  "data_gaps": ["이 분석을 개선했을 구체적 데이터 (한국어)"]
}
"""


@dataclass
class ResearchResult:
    business_summary: str
    growth_drivers: list[str]
    quality_notes: str
    competitive_position: str
    catalysts: list[dict]
    data_gaps: list[str]
    raw_response_tokens: tuple[int, int]  # (input, output)


class ResearchAgent:
    def __init__(self, llm: LLMProvider):
        self._llm = llm

    def run(self, ticker: str, facts: dict) -> ResearchResult:
        if not self._llm.is_configured():
            return ResearchResult(
                business_summary="DATA_NOT_AVAILABLE (LLM not configured — set ANTHROPIC_API_KEY)",
                growth_drivers=[],
                quality_notes="DATA_NOT_AVAILABLE",
                competitive_position="DATA_NOT_AVAILABLE",
                catalysts=[],
                data_gaps=["LLM not configured"],
                raw_response_tokens=(0, 0),
            )

        prompt = f"Ticker: {ticker}\n\nFacts:\n{json.dumps(facts, indent=2, default=str)}"
        try:
            response = self._llm.complete(system=_SYSTEM_PROMPT, prompt=prompt, max_tokens=4000)
        except Exception as exc:
            logger.error("Research agent LLM call failed for %s: %s", ticker, exc)
            return ResearchResult(
                business_summary=f"DATA_NOT_AVAILABLE (LLM call failed: {exc})",
                growth_drivers=[],
                quality_notes="DATA_NOT_AVAILABLE",
                competitive_position="DATA_NOT_AVAILABLE",
                catalysts=[],
                data_gaps=["LLM call failed"],
                raw_response_tokens=(0, 0),
            )
        try:
            parsed = extract_json(response.text)
        except LLMJsonParseError as exc:
            reason = "response was truncated at max_tokens" if response.stop_reason == "max_tokens" else str(exc)
            logger.warning("Research agent JSON parse failed for %s: %s", ticker, reason)
            return ResearchResult(
                business_summary=f"DATA_NOT_AVAILABLE (LLM response could not be parsed: {reason})",
                growth_drivers=[],
                quality_notes="DATA_NOT_AVAILABLE",
                competitive_position="DATA_NOT_AVAILABLE",
                catalysts=[],
                data_gaps=[f"LLM response parse failure ({reason})"],
                raw_response_tokens=(response.input_tokens, response.output_tokens),
            )

        return ResearchResult(
            business_summary=parsed.get("business_summary", "DATA_NOT_AVAILABLE"),
            growth_drivers=parsed.get("growth_drivers", []),
            quality_notes=parsed.get("quality_notes", "DATA_NOT_AVAILABLE"),
            competitive_position=parsed.get("competitive_position", "DATA_NOT_AVAILABLE"),
            catalysts=parsed.get("catalysts", []),
            data_gaps=parsed.get("data_gaps", []),
            raw_response_tokens=(response.input_tokens, response.output_tokens),
        )
