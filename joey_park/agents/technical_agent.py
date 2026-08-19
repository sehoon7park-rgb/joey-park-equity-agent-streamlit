"""Technical / Market Agent — price/volume/trend/momentum. Deterministic;
no LLM calls.
"""
from __future__ import annotations

from dataclasses import dataclass

from joey_park.analytics.scoring import score_momentum
from joey_park.data.models import DataStatus, MarketSnapshot


@dataclass
class TechnicalResult:
    momentum_score: float | None
    trend_description: str


class TechnicalAgent:
    def run(self, market: MarketSnapshot) -> TechnicalResult:
        score = score_momentum(market)
        description = self._describe_trend(market)
        return TechnicalResult(momentum_score=score, trend_description=description)

    @staticmethod
    def _describe_trend(market: MarketSnapshot) -> str:
        if len(market.price_history) < 50:
            return "DATA_NOT_AVAILABLE (insufficient price history)"
        closes = [bar.close for bar in market.price_history]
        last = closes[-1]
        ma50 = sum(closes[-50:]) / 50
        above_ma50 = last > ma50
        high52 = market.fifty_two_week_high.value if market.fifty_two_week_high.status == DataStatus.OK else None
        low52 = market.fifty_two_week_low.value if market.fifty_two_week_low.status == DataStatus.OK else None
        range_note = ""
        if high52 and low52 and high52 != low52:
            pct = (last - low52) / (high52 - low52)
            range_note = f", {pct:.0%} of the way through its 52-week range"
        return f"Price is {'above' if above_ma50 else 'below'} its 50-day average{range_note}."
