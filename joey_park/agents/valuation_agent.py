"""Valuation Agent — multi-method valuation, sector-aware (master-spec
section 24). Deterministic; no LLM calls.
"""
from __future__ import annotations

from dataclasses import dataclass

from joey_park.analytics.scoring import score_valuation
from joey_park.analytics.valuation_methods import ValuationVerdict, evaluate
from joey_park.data.models import FinancialSnapshot, MarketSnapshot


@dataclass
class ValuationResult:
    valuation_score: float | None
    verdicts: list[ValuationVerdict]


class ValuationAgent:
    def __init__(self, methods_by_sector: dict, heuristics: dict):
        self._methods_by_sector = methods_by_sector
        self._heuristics = heuristics

    def run(self, financials: FinancialSnapshot, market: MarketSnapshot) -> ValuationResult:
        verdicts = evaluate(financials, market, financials.sector, self._methods_by_sector, self._heuristics)
        score = score_valuation(financials, market, self._heuristics)
        return ValuationResult(valuation_score=score, verdicts=verdicts)
