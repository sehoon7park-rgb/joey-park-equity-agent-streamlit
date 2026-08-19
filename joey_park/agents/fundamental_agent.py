"""Fundamental Agent — deterministic ratio calculation + a structured fact
summary for downstream narrative agents to cite. No LLM calls here.
"""
from __future__ import annotations

from dataclasses import dataclass

from joey_park.analytics.scoring import score_fundamental, score_growth, score_quality
from joey_park.data.models import DataStatus, FinancialSnapshot


@dataclass
class FundamentalResult:
    fundamental_score: float | None
    growth_score: float | None
    quality_score: float | None
    facts_summary: dict


def _fmt(fact) -> dict:
    return {
        "value": fact.value,
        "status": fact.status.value,
        "source": fact.source,
        "period_date": fact.period_date.isoformat() if fact.period_date else None,
        "available_date": fact.available_date.isoformat() if fact.available_date else None,
    }


class FundamentalAgent:
    def run(self, financials: FinancialSnapshot) -> FundamentalResult:
        facts_summary = {
            "revenue": _fmt(financials.revenue),
            "revenue_yoy_growth": _fmt(financials.revenue_yoy_growth),
            "gross_margin": _fmt(financials.gross_margin),
            "operating_margin": _fmt(financials.operating_margin),
            "fcf": _fmt(financials.fcf),
            "fcf_margin": _fmt(financials.fcf_margin),
            "net_debt": _fmt(financials.net_debt),
            "roe": _fmt(financials.roe),
        }
        return FundamentalResult(
            fundamental_score=score_fundamental(financials),
            growth_score=score_growth(financials),
            quality_score=score_quality(financials),
            facts_summary=facts_summary,
        )
