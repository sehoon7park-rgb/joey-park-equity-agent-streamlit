"""Critic / Verification Agent — the second LLM call, per master-spec
section 21. Reviews the Research Agent's narrative against the raw facts
before the Decision Agent is allowed to synthesize a final view.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from joey_park.llm.base import LLMProvider
from joey_park.llm.json_utils import LLMJsonParseError, extract_json

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the Critic / Verification Agent inside the Joey Park U.S. Equity Investment Agent.

You will be given (1) the raw sourced facts about a company and (2) a narrative another agent
wrote from those facts. Check the narrative against the facts and answer, honestly and
skeptically, the verification checklist below. Your job is to catch problems, not to be agreeable.

CHECKLIST:
1. Does every number in the narrative actually appear in the provided facts?
2. Is the narrative one-sided (bull case emphasized, bear case or risks missing/thin)?
3. Are valuation assumptions (if any) reasonable, or do they assume best-case outcomes?
4. Does the narrative acknowledge data gaps / DATA_NOT_AVAILABLE points instead of glossing over them?
5. Is there any claim that contradicts another fact in the provided data?

LENGTH: List at most 5 items in "issues" and 3 in "contradictions", each 1-2 sentences — be
specific but concise, not exhaustive. This is a hard limit; your response must fit well within
the token budget.

LANGUAGE: Write the text VALUES inside "contradictions" and "issues" in natural, professional
Korean (한국어). JSON KEYS, the boolean true/false values, and the "verdict" value ("PASS" or
"NEEDS_REVISION") must stay in English exactly as specified — do not translate those.

Respond with ONLY a JSON object:
{
  "numbers_match_facts": true/false,
  "bull_only_bias_detected": true/false,
  "missing_bear_case": true/false,
  "valuation_assumptions_reasonable": true/false,
  "data_gaps_acknowledged": true/false,
  "contradictions": ["구체적 모순점 1 (한국어)", ...],
  "issues": ["구체적 문제점 1 (한국어)", ...],
  "verdict": "PASS" or "NEEDS_REVISION"
}
"""


@dataclass
class CriticResult:
    numbers_match_facts: bool
    bull_only_bias_detected: bool
    missing_bear_case: bool
    valuation_assumptions_reasonable: bool
    data_gaps_acknowledged: bool
    contradictions: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    verdict: str = "NOT_RUN"


class CriticAgent:
    def __init__(self, llm: LLMProvider):
        self._llm = llm

    def run(self, ticker: str, facts: dict, research_narrative: dict) -> CriticResult:
        if not self._llm.is_configured():
            return CriticResult(
                numbers_match_facts=False,
                bull_only_bias_detected=False,
                missing_bear_case=False,
                valuation_assumptions_reasonable=False,
                data_gaps_acknowledged=False,
                issues=["LLM not configured — critic pass skipped, confidence should be capped at Low"],
                verdict="NOT_RUN",
            )

        prompt = (
            f"Ticker: {ticker}\n\n"
            f"Facts:\n{json.dumps(facts, indent=2, default=str)}\n\n"
            f"Narrative to review:\n{json.dumps(research_narrative, indent=2, default=str)}"
        )
        try:
            response = self._llm.complete(system=_SYSTEM_PROMPT, prompt=prompt, max_tokens=3800)
        except Exception as exc:
            logger.error("Critic agent LLM call failed for %s: %s", ticker, exc)
            return CriticResult(
                numbers_match_facts=False,
                bull_only_bias_detected=False,
                missing_bear_case=False,
                valuation_assumptions_reasonable=False,
                data_gaps_acknowledged=False,
                issues=[f"Critic LLM call failed: {exc}"],
                verdict="NOT_RUN",
            )
        try:
            parsed = extract_json(response.text)
        except LLMJsonParseError as exc:
            reason = "response was truncated at max_tokens" if response.stop_reason == "max_tokens" else str(exc)
            logger.warning("Critic agent JSON parse failed for %s: %s", ticker, reason)
            return CriticResult(
                numbers_match_facts=False,
                bull_only_bias_detected=False,
                missing_bear_case=False,
                valuation_assumptions_reasonable=False,
                data_gaps_acknowledged=False,
                issues=[f"Critic LLM response could not be parsed ({reason})"],
                verdict="NEEDS_REVISION",
            )

        return CriticResult(
            numbers_match_facts=bool(parsed.get("numbers_match_facts", False)),
            bull_only_bias_detected=bool(parsed.get("bull_only_bias_detected", False)),
            missing_bear_case=bool(parsed.get("missing_bear_case", False)),
            valuation_assumptions_reasonable=bool(parsed.get("valuation_assumptions_reasonable", False)),
            data_gaps_acknowledged=bool(parsed.get("data_gaps_acknowledged", False)),
            contradictions=parsed.get("contradictions", []),
            issues=parsed.get("issues", []),
            verdict=parsed.get("verdict", "NEEDS_REVISION"),
        )
