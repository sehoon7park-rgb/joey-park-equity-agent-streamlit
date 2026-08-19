"""Risk Agent — position-level and (if holdings are supplied) portfolio-level
risk. Deterministic; no LLM calls.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from joey_park.data.models import DataStatus, MarketSnapshot


@dataclass
class PositionRisk:
    annualized_volatility: float | None
    beta: float | None
    max_drawdown_1y: float | None
    notes: list[str]


@dataclass
class PortfolioRisk:
    single_position_pct: float | None
    sector_pct: float | None
    single_position_breach: bool
    sector_breach: bool
    notes: list[str]


class RiskAgent:
    def run_position_risk(self, market: MarketSnapshot) -> PositionRisk:
        notes: list[str] = []
        closes = [bar.close for bar in market.price_history]
        vol = None
        max_dd = None
        if len(closes) >= 30:
            returns = [(closes[i] / closes[i - 1]) - 1 for i in range(1, len(closes))]
            vol = statistics.pstdev(returns) * (252**0.5)
            peak = closes[0]
            max_dd = 0.0
            for c in closes:
                peak = max(peak, c)
                dd = (c - peak) / peak
                max_dd = min(max_dd, dd)
        else:
            notes.append("가격 데이터가 30일 미만이라 변동성/최대낙폭을 계산하지 않았습니다.")

        beta = market.beta.value if market.beta and market.beta.status == DataStatus.OK else None
        if beta is None:
            notes.append("데이터 제공자로부터 베타 값을 받아오지 못했습니다.")

        return PositionRisk(annualized_volatility=vol, beta=beta, max_drawdown_1y=max_dd, notes=notes)

    def run_portfolio_risk(
        self,
        ticker: str,
        position_market_value: float,
        sector: str | None,
        all_positions: list[dict],  # [{ticker, market_value, sector}]
        max_single_position_pct: float,
        max_sector_pct: float,
    ) -> PortfolioRisk:
        total_value = sum(p["market_value"] for p in all_positions) or position_market_value
        if total_value == 0:
            return PortfolioRisk(None, None, False, False, ["평가금액이 0이라 비중을 계산할 수 없습니다."])

        single_pct = position_market_value / total_value
        sector_value = sum(p["market_value"] for p in all_positions if p.get("sector") == sector) if sector else 0.0
        sector_pct = sector_value / total_value if sector else None

        notes = []
        single_breach = single_pct > max_single_position_pct
        if single_breach:
            notes.append(f"{ticker}이(가) 포트폴리오의 {single_pct:.1%}를 차지 — 한도 {max_single_position_pct:.0%} 초과")
        sector_breach = bool(sector_pct and sector_pct > max_sector_pct)
        if sector_breach:
            notes.append(f"섹터 '{sector}'가 포트폴리오의 {sector_pct:.1%}를 차지 — 한도 {max_sector_pct:.0%} 초과")

        return PortfolioRisk(
            single_position_pct=single_pct,
            sector_pct=sector_pct,
            single_position_breach=single_breach,
            sector_breach=sector_breach,
            notes=notes,
        )
