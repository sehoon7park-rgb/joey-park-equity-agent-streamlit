"""Portfolio Agent — cross-position view (master-spec section 16). Only
runs meaningfully once positions exist in the DB; deterministic, no LLM.
"""
from __future__ import annotations

from dataclasses import dataclass

from joey_park.agents.risk_agent import PortfolioRisk, RiskAgent


@dataclass
class SectorExposure:
    sector: str
    market_value: float
    pct_of_portfolio: float


@dataclass
class ConcentrationWarning:
    """Structured, not pre-formatted text, so callers (UI/CLI/report) can
    render the message in whatever language/format they use — see the
    language contract in ui/app.py's module docstring.
    """

    kind: str  # "sector" or "position"
    label: str  # sector name or ticker
    pct: float
    limit: float


@dataclass
class PortfolioSummary:
    total_market_value: float
    sector_exposures: list[SectorExposure]
    concentration_warnings: list[ConcentrationWarning]


class PortfolioAgent:
    def __init__(self, risk_agent: RiskAgent, max_single_position_pct: float, max_sector_pct: float):
        self._risk_agent = risk_agent
        self._max_single = max_single_position_pct
        self._max_sector = max_sector_pct

    def summarize(self, positions: list[dict]) -> PortfolioSummary:
        """positions: [{ticker, market_value, sector}]"""
        total = sum(p["market_value"] for p in positions)
        by_sector: dict[str, float] = {}
        for p in positions:
            sector = p.get("sector") or "Unknown"
            by_sector[sector] = by_sector.get(sector, 0.0) + p["market_value"]

        exposures = [
            SectorExposure(sector=s, market_value=v, pct_of_portfolio=(v / total if total else 0.0))
            for s, v in sorted(by_sector.items(), key=lambda kv: -kv[1])
        ]

        warnings: list[ConcentrationWarning] = []
        for exp in exposures:
            if exp.pct_of_portfolio > self._max_sector:
                warnings.append(ConcentrationWarning("sector", exp.sector, exp.pct_of_portfolio, self._max_sector))
        for p in positions:
            pct = p["market_value"] / total if total else 0.0
            if pct > self._max_single:
                warnings.append(ConcentrationWarning("position", p["ticker"], pct, self._max_single))

        return PortfolioSummary(total_market_value=total, sector_exposures=exposures, concentration_warnings=warnings)

    def position_impact(self, ticker: str, market_value: float, sector: str | None, positions: list[dict]) -> PortfolioRisk:
        return self._risk_agent.run_portfolio_risk(
            ticker, market_value, sector, positions, self._max_single, self._max_sector
        )
