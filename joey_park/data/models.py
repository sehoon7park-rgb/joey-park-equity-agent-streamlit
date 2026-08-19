"""Data models shared across providers and agents.

Every fact carries its own provenance: `source`, `period_date` (what period
the number describes) and `available_date` (when it was actually knowable),
plus `retrieval_timestamp` (when this run fetched it). This is what makes
point-in-time / look-ahead-bias-safe analysis possible later, even though
the MVP doesn't backtest yet (see docs/DECISION_LOG.md D5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


class SourceTier(str, Enum):
    TIER_1_OFFICIAL = "TIER_1_OFFICIAL"        # SEC filings, XBRL company facts
    TIER_2_MARKET_DATA = "TIER_2_MARKET_DATA"  # yfinance price/fundamentals
    TIER_3_NEWS_RESEARCH = "TIER_3_NEWS_RESEARCH"
    TIER_4_LLM_INTERPRETATION = "TIER_4_LLM_INTERPRETATION"


class DataStatus(str, Enum):
    OK = "OK"
    DATA_NOT_AVAILABLE = "DATA_NOT_AVAILABLE"
    DATA_STALE = "DATA_STALE"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


@dataclass(frozen=True)
class Fact:
    """A single sourced data point."""

    value: Any
    source: str
    tier: SourceTier
    period_date: date | None
    available_date: date | None
    retrieval_timestamp: datetime
    status: DataStatus = DataStatus.OK

    @classmethod
    def unavailable(cls, source: str, tier: SourceTier) -> "Fact":
        return cls(
            value=None,
            source=source,
            tier=tier,
            period_date=None,
            available_date=None,
            retrieval_timestamp=datetime.now(timezone.utc),
            status=DataStatus.DATA_NOT_AVAILABLE,
        )


@dataclass
class PriceBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float | None = None


@dataclass
class MarketSnapshot:
    ticker: str
    as_of: datetime
    last_price: Fact
    price_history: list[PriceBar] = field(default_factory=list)
    market_cap: Fact | None = None
    beta: Fact | None = None
    fifty_two_week_high: Fact | None = None
    fifty_two_week_low: Fact | None = None


@dataclass
class FinancialSnapshot:
    """Normalized fundamentals for one ticker, most-recent-period values.

    All fields are `Fact` so missing data is explicit (`DATA_NOT_AVAILABLE`)
    rather than silently coerced to 0 or None.
    """

    ticker: str
    fiscal_period_end: date | None
    revenue: Fact
    revenue_yoy_growth: Fact
    gross_margin: Fact
    operating_margin: Fact
    fcf: Fact
    fcf_margin: Fact
    net_debt: Fact
    total_debt: Fact
    cash: Fact
    roe: Fact
    roic: Fact
    eps_ttm: Fact
    forward_pe: Fact
    trailing_pe: Fact
    ev_to_ebitda: Fact
    ev_to_revenue: Fact
    price_to_book: Fact
    peg_ratio: Fact
    sector: str | None = None
    industry: str | None = None


@dataclass
class DataQualityReport:
    ticker: str
    checks_run: list[str]
    warnings: list[str]
    completeness_pct: float
    passed: bool
