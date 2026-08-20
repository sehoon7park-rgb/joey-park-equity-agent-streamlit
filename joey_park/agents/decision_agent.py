"""Decision Agent — the third and final LLM call. Synthesizes everything
(quant scores, research narrative, critic findings) into a structured
Investment View. Confidence is derived from evidence quality (data
completeness + critic verdict), kept explicitly separate from the score
itself (master-spec section 11).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from joey_park.llm.base import LLMProvider
from joey_park.llm.errors import describe_with_traceback as describe  # TEMP: full traceback for cloud-only bug diagnosis
from joey_park.llm.json_utils import LLMJsonParseError, extract_json

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the Decision Agent inside the Joey Park U.S. Equity Investment Agent.

You will be given: quantitative dimension scores (0-1, already computed deterministically —
do not recompute or contradict them), a research narrative, critic-agent findings, and macro
risk flags. Synthesize a structured Investment View.

HARD RULES:
- Confidence reflects EVIDENCE QUALITY (data completeness, critic verdict, data gaps), not how
  attractive the opportunity looks. A great business with thin data is still Low confidence.
- If the critic flagged bull_only_bias_detected or missing_bear_case, your bear_case must be
  substantive, not token.
- Every scenario (bull/base/bear) must include a probability, and the three probabilities
  should be a reasonable partition (do not make bull 90% and bear 5% without strong justification
  in the facts).
- "what_would_change_my_mind" must name a SPECIFIC, checkable condition (a metric threshold or
  event), not a vague statement like "if things change".
- If overall_score or data completeness is very low, investment_view should lean Neutral and
  confidence should be Low — do not force a strong opinion out of weak data.

LANGUAGE: Write every narrative/text VALUE (thesis, bull_case.narrative, base_case.narrative,
bear_case.narrative, valuation_summary, catalysts entries, risks entries,
what_would_change_my_mind) in natural, professional Korean (한국어), as if writing for a
Korean-speaking investor. JSON KEYS stay in English exactly as shown. The three enum fields —
"investment_view" (Bullish/Neutral/Bearish), "confidence" (High/Medium/Low), and "time_horizon"
(Short/Medium/Long) — MUST use exactly those English words unchanged (the app maps them to
Korean for display and compares them programmatically elsewhere, so translating them here would
break the app). "probability" values stay numeric. The literal sentinel "DATA_NOT_AVAILABLE"
should only appear verbatim when an entire field is undeterminable; a partial gap mentioned
inside otherwise-Korean prose should just be described in Korean.

Respond with ONLY a JSON object matching this shape:
{
  "investment_view": "Bullish" | "Neutral" | "Bearish",
  "confidence": "High" | "Medium" | "Low",
  "time_horizon": "Short" | "Medium" | "Long",
  "thesis": "핵심 투자논지 2-4문장 (한국어)",
  "bull_case": {"narrative": "낙관 시나리오 (한국어)", "probability": 0.0},
  "base_case": {"narrative": "기본 시나리오 (한국어)", "probability": 0.0},
  "bear_case": {"narrative": "비관 시나리오 (한국어)", "probability": 0.0},
  "valuation_summary": "현재 밸류에이션과 위 시나리오 비교 1-3문장 (한국어)",
  "catalysts": ["구체적 향후 촉매 1 (한국어)", ...],
  "risks": ["구체적 리스크 1, 논지를 무너뜨릴 수 있는 것 (한국어)", ...],
  "what_would_change_my_mind": "구체적이고 확인 가능한 조건 (한국어)"
}
"""


@dataclass
class DecisionResult:
    investment_view: str
    confidence: str
    time_horizon: str
    thesis: str
    bull_case: dict
    base_case: dict
    bear_case: dict
    valuation_summary: str
    catalysts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    what_would_change_my_mind: str = "DATA_NOT_AVAILABLE"


class DecisionAgent:
    def __init__(self, llm: LLMProvider):
        self._llm = llm

    def run(
        self,
        ticker: str,
        dimension_scores: dict,
        overall_score: float | None,
        completeness_pct: float,
        research_narrative: dict,
        critic_result: dict,
        macro_risk_flags: dict,
    ) -> DecisionResult:
        if not self._llm.is_configured():
            return DecisionResult(
                investment_view="Neutral",
                confidence="Low",
                time_horizon="Medium",
                thesis="DATA_NOT_AVAILABLE (LLM not configured — set ANTHROPIC_API_KEY)",
                bull_case={"narrative": "DATA_NOT_AVAILABLE", "probability": 0.0},
                base_case={"narrative": "DATA_NOT_AVAILABLE", "probability": 0.0},
                bear_case={"narrative": "DATA_NOT_AVAILABLE", "probability": 0.0},
                valuation_summary="DATA_NOT_AVAILABLE",
                what_would_change_my_mind="Configure ANTHROPIC_API_KEY to enable the Decision Agent.",
            )

        payload = {
            "dimension_scores": dimension_scores,
            "overall_score": overall_score,
            "data_completeness_pct": completeness_pct,
            "research_narrative": research_narrative,
            "critic_findings": critic_result,
            "macro_risk_flags": macro_risk_flags,
        }
        prompt = f"Ticker: {ticker}\n\n{json.dumps(payload, indent=2, default=str)}"
        try:
            response = self._llm.complete(system=_SYSTEM_PROMPT, prompt=prompt, max_tokens=4500)
        except Exception as exc:
            detail = describe(exc)
            logger.error("Decision agent LLM call failed for %s: %s", ticker, detail)
            return DecisionResult(
                investment_view="Neutral",
                confidence="Low",
                time_horizon="Medium",
                thesis=f"DATA_NOT_AVAILABLE (Decision agent LLM call failed: {detail})",
                bull_case={"narrative": "DATA_NOT_AVAILABLE", "probability": 0.0},
                base_case={"narrative": "DATA_NOT_AVAILABLE", "probability": 0.0},
                bear_case={"narrative": "DATA_NOT_AVAILABLE", "probability": 0.0},
                valuation_summary="DATA_NOT_AVAILABLE",
                what_would_change_my_mind="Re-run once the LLM provider is reachable.",
            )
        try:
            parsed = extract_json(response.text)
        except LLMJsonParseError as exc:
            reason = "response was truncated at max_tokens" if response.stop_reason == "max_tokens" else str(exc)
            logger.warning("Decision agent JSON parse failed for %s: %s", ticker, reason)
            return DecisionResult(
                investment_view="Neutral",
                confidence="Low",
                time_horizon="Medium",
                thesis=f"DATA_NOT_AVAILABLE (Decision agent response could not be parsed: {reason})",
                bull_case={"narrative": "DATA_NOT_AVAILABLE", "probability": 0.0},
                base_case={"narrative": "DATA_NOT_AVAILABLE", "probability": 0.0},
                bear_case={"narrative": "DATA_NOT_AVAILABLE", "probability": 0.0},
                valuation_summary="DATA_NOT_AVAILABLE",
                what_would_change_my_mind="Re-run once the Decision Agent response can be parsed.",
            )

        return DecisionResult(
            investment_view=parsed.get("investment_view", "Neutral"),
            confidence=parsed.get("confidence", "Low"),
            time_horizon=parsed.get("time_horizon", "Medium"),
            thesis=parsed.get("thesis", "DATA_NOT_AVAILABLE"),
            bull_case=parsed.get("bull_case", {}),
            base_case=parsed.get("base_case", {}),
            bear_case=parsed.get("bear_case", {}),
            valuation_summary=parsed.get("valuation_summary", "DATA_NOT_AVAILABLE"),
            catalysts=parsed.get("catalysts", []),
            risks=parsed.get("risks", []),
            what_would_change_my_mind=parsed.get("what_would_change_my_mind", "DATA_NOT_AVAILABLE"),
        )
