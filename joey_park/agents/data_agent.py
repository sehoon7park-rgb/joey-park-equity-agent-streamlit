"""Data Agent — fetches and normalizes price/fundamentals/filings/macro data.

Deterministic, no LLM. Each sub-fetch is isolated with try/except so one
provider failing (e.g. SEC EDGAR rate limit) doesn't take down the others
(master-spec section 36: "one API or Agent failing must not halt the whole
system").
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from joey_park.data.models import FinancialSnapshot, MarketSnapshot
from joey_park.data.providers.fred_provider import FredProvider
from joey_park.data.providers.sec_edgar_provider import SecEdgarProvider
from joey_park.data.providers.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)


@dataclass
class DataBundle:
    ticker: str
    market: MarketSnapshot
    financials: FinancialSnapshot
    sec_facts: dict
    sec_recent_filings: list[dict]
    macro_facts: dict
    sources_used: list[str]
    errors: list[str]


class DataAgent:
    def __init__(self, yfinance: YFinanceProvider, sec_edgar: SecEdgarProvider, fred: FredProvider):
        self._yf = yfinance
        self._sec = sec_edgar
        self._fred = fred

    def fetch(self, ticker: str) -> DataBundle:
        sources_used: list[str] = []
        errors: list[str] = []

        try:
            market = self._yf.fetch_market_snapshot(ticker)
            sources_used.append("yfinance:market")
        except Exception as exc:
            logger.error("Market snapshot fetch failed for %s: %s", ticker, exc)
            errors.append(f"market_snapshot: {exc}")
            from joey_park.data.models import DataStatus, Fact, SourceTier
            market = MarketSnapshot(
                ticker=ticker,
                as_of=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                last_price=Fact.unavailable("yfinance", SourceTier.TIER_2_MARKET_DATA),
            )

        try:
            financials = self._yf.fetch_financial_snapshot(ticker)
            sources_used.append("yfinance:fundamentals")
        except Exception as exc:
            logger.error("Financial snapshot fetch failed for %s: %s", ticker, exc)
            errors.append(f"financial_snapshot: {exc}")
            financials = self._empty_financials(ticker)

        try:
            sec_facts = self._sec.fetch_company_facts(ticker)
            sources_used.append("sec_edgar:companyfacts")
        except Exception as exc:
            logger.error("SEC company facts fetch failed for %s: %s", ticker, exc)
            errors.append(f"sec_company_facts: {exc}")
            sec_facts = {}

        try:
            sec_filings = self._sec.fetch_recent_filings(ticker)
            sources_used.append("sec_edgar:submissions")
        except Exception as exc:
            logger.error("SEC filings fetch failed for %s: %s", ticker, exc)
            errors.append(f"sec_filings: {exc}")
            sec_filings = []

        try:
            macro_facts = self._fred.fetch_all() if self._fred.is_configured() else {}
            if macro_facts:
                sources_used.append("fred")
        except Exception as exc:
            logger.error("FRED fetch failed: %s", exc)
            errors.append(f"fred: {exc}")
            macro_facts = {}

        return DataBundle(
            ticker=ticker,
            market=market,
            financials=financials,
            sec_facts=sec_facts,
            sec_recent_filings=sec_filings,
            macro_facts=macro_facts,
            sources_used=sources_used,
            errors=errors,
        )

    @staticmethod
    def _empty_financials(ticker: str) -> FinancialSnapshot:
        from joey_park.data.models import DataStatus, Fact, SourceTier

        na = lambda: Fact.unavailable("yfinance", SourceTier.TIER_2_MARKET_DATA)
        return FinancialSnapshot(
            ticker=ticker,
            fiscal_period_end=None,
            revenue=na(), revenue_yoy_growth=na(), gross_margin=na(), operating_margin=na(),
            fcf=na(), fcf_margin=na(), net_debt=na(), total_debt=na(), cash=na(), roe=na(),
            roic=na(), eps_ttm=na(), forward_pe=na(), trailing_pe=na(), ev_to_ebitda=na(),
            ev_to_revenue=na(), price_to_book=na(), peg_ratio=na(),
        )
