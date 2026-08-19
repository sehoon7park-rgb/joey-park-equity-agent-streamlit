"""Free/public market data provider backed by yfinance (Tier 2: unofficial
but widely used market data — see docs/SOURCE_COMPARISON.md D9).

yfinance does not expose the actual filing/release date for fundamentals, so
`available_date` for those facts is estimated as `period_date + 45 days`
(a conservative typical 10-Q/10-K reporting lag). This is a heuristic, not a
measurement — SECEdgarProvider supplies exact filing dates and should be
preferred wherever precision matters (e.g. backtesting, once built).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from joey_park.data.models import (
    DataStatus,
    Fact,
    FinancialSnapshot,
    MarketSnapshot,
    PriceBar,
    SourceTier,
)

logger = logging.getLogger(__name__)

_FUNDAMENTALS_LAG_DAYS = 45
_SOURCE = "yfinance"
_TIER = SourceTier.TIER_2_MARKET_DATA


def _fact(value, period_date: date | None) -> Fact:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return Fact.unavailable(_SOURCE, _TIER)
    available_date = period_date + timedelta(days=_FUNDAMENTALS_LAG_DAYS) if period_date else None
    return Fact(
        value=value,
        source=_SOURCE,
        tier=_TIER,
        period_date=period_date,
        available_date=available_date,
        retrieval_timestamp=datetime.now(timezone.utc),
        status=DataStatus.OK,
    )


def _safe_ratio(numerator, denominator):
    try:
        if numerator is None or denominator in (None, 0):
            return None
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _fetch_ticker(ticker: str) -> yf.Ticker:
    return yf.Ticker(ticker)


class YFinanceProvider:
    """Fetches and normalizes price + fundamentals for a single ticker."""

    def fetch_market_snapshot(self, ticker: str, lookback_days: int = 400) -> MarketSnapshot:
        t = _fetch_ticker(ticker)
        try:
            info = t.info or {}
        except Exception as exc:  # yfinance raises broadly on network/parse failures
            logger.warning("yfinance info fetch failed for %s: %s", ticker, exc)
            info = {}

        try:
            hist = t.history(period=f"{lookback_days}d", auto_adjust=False)
        except Exception as exc:
            logger.warning("yfinance history fetch failed for %s: %s", ticker, exc)
            hist = pd.DataFrame()

        bars: list[PriceBar] = []
        last_price_fact = Fact.unavailable(_SOURCE, _TIER)
        if not hist.empty:
            for idx, row in hist.iterrows():
                bars.append(
                    PriceBar(
                        date=idx.date(),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                        adj_close=float(row["Adj Close"]) if "Adj Close" in row else None,
                    )
                )
            last_row = hist.iloc[-1]
            last_date = hist.index[-1].date()
            last_price_fact = _fact(float(last_row["Close"]), last_date)

        as_of = datetime.now(timezone.utc)
        return MarketSnapshot(
            ticker=ticker,
            as_of=as_of,
            last_price=last_price_fact,
            price_history=bars,
            market_cap=_fact(info.get("marketCap"), date.today()),
            beta=_fact(info.get("beta"), date.today()),
            fifty_two_week_high=_fact(info.get("fiftyTwoWeekHigh"), date.today()),
            fifty_two_week_low=_fact(info.get("fiftyTwoWeekLow"), date.today()),
        )

    def fetch_financial_snapshot(self, ticker: str) -> FinancialSnapshot:
        t = _fetch_ticker(ticker)
        try:
            info = t.info or {}
        except Exception as exc:
            logger.warning("yfinance info fetch failed for %s: %s", ticker, exc)
            info = {}

        income_stmt = self._safe_df(lambda: t.quarterly_financials)
        cashflow = self._safe_df(lambda: t.quarterly_cashflow)
        balance_sheet = self._safe_df(lambda: t.quarterly_balance_sheet)

        period_date = None
        if income_stmt is not None and not income_stmt.empty:
            period_date = income_stmt.columns[0].date()

        revenue = self._row_value(income_stmt, "Total Revenue")
        revenue_prior_year = self._row_value(income_stmt, "Total Revenue", col_index=4)
        gross_profit = self._row_value(income_stmt, "Gross Profit")
        operating_income = self._row_value(income_stmt, "Operating Income")
        fcf = self._row_value(cashflow, "Free Cash Flow")
        total_debt = self._row_value(balance_sheet, "Total Debt")
        cash = self._row_value(balance_sheet, "Cash And Cash Equivalents")

        revenue_yoy = _safe_ratio(
            (revenue - revenue_prior_year) if revenue and revenue_prior_year else None,
            revenue_prior_year,
        )
        gross_margin = _safe_ratio(gross_profit, revenue)
        operating_margin = _safe_ratio(operating_income, revenue)
        fcf_margin = _safe_ratio(fcf, revenue)
        net_debt = (total_debt - cash) if (total_debt is not None and cash is not None) else None

        return FinancialSnapshot(
            ticker=ticker,
            fiscal_period_end=period_date,
            revenue=_fact(revenue, period_date),
            revenue_yoy_growth=_fact(revenue_yoy, period_date),
            gross_margin=_fact(gross_margin, period_date),
            operating_margin=_fact(operating_margin, period_date),
            fcf=_fact(fcf, period_date),
            fcf_margin=_fact(fcf_margin, period_date),
            net_debt=_fact(net_debt, period_date),
            total_debt=_fact(total_debt, period_date),
            cash=_fact(cash, period_date),
            roe=_fact(info.get("returnOnEquity"), period_date),
            roic=Fact.unavailable(_SOURCE, _TIER),  # not exposed by yfinance; needs invested-capital calc
            eps_ttm=_fact(info.get("trailingEps"), period_date),
            forward_pe=_fact(info.get("forwardPE"), date.today()),
            trailing_pe=_fact(info.get("trailingPE"), date.today()),
            ev_to_ebitda=_fact(info.get("enterpriseToEbitda"), date.today()),
            ev_to_revenue=_fact(info.get("enterpriseToRevenue"), date.today()),
            price_to_book=_fact(info.get("priceToBook"), date.today()),
            peg_ratio=_fact(info.get("trailingPegRatio") or info.get("pegRatio"), date.today()),
            sector=info.get("sector"),
            industry=info.get("industry"),
        )

    @staticmethod
    def _safe_df(getter):
        try:
            df = getter()
            return df if df is not None and not df.empty else None
        except Exception as exc:
            logger.warning("yfinance statement fetch failed: %s", exc)
            return None

    @staticmethod
    def _row_value(df: pd.DataFrame | None, row_name: str, col_index: int = 0) -> float | None:
        if df is None or row_name not in df.index:
            return None
        try:
            val = df.loc[row_name].iloc[col_index]
            return None if pd.isna(val) else float(val)
        except (IndexError, KeyError):
            return None
