import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from joey_park.data.models import (  # noqa: E402
    DataStatus,
    Fact,
    FinancialSnapshot,
    MarketSnapshot,
    PriceBar,
    SourceTier,
)


def make_fact(value, status=DataStatus.OK, period_date=None, tier=SourceTier.TIER_2_MARKET_DATA, source="test"):
    return Fact(
        value=value,
        source=source,
        tier=tier,
        period_date=period_date or date(2026, 6, 30),
        available_date=period_date or date(2026, 6, 30),
        retrieval_timestamp=datetime.utcnow(),
        status=status,
    )


def na_fact():
    return Fact.unavailable("test", SourceTier.TIER_2_MARKET_DATA)


@pytest.fixture
def healthy_financials():
    return FinancialSnapshot(
        ticker="TEST",
        fiscal_period_end=date(2026, 6, 30),
        revenue=make_fact(1_000_000_000),
        revenue_yoy_growth=make_fact(0.25),
        gross_margin=make_fact(0.65),
        operating_margin=make_fact(0.25),
        fcf=make_fact(200_000_000),
        fcf_margin=make_fact(0.20),
        net_debt=make_fact(-500_000_000),  # net cash
        total_debt=make_fact(100_000_000),
        cash=make_fact(600_000_000),
        roe=make_fact(0.22),
        roic=na_fact(),
        eps_ttm=make_fact(3.5),
        forward_pe=make_fact(22.0),
        trailing_pe=make_fact(28.0),
        ev_to_ebitda=make_fact(15.0),
        ev_to_revenue=make_fact(6.0),
        price_to_book=make_fact(8.0),
        peg_ratio=make_fact(1.2),
        sector="ai_software_cloud",
        industry="Software",
    )


@pytest.fixture
def sparse_financials():
    return FinancialSnapshot(
        ticker="THIN",
        fiscal_period_end=None,
        revenue=na_fact(),
        revenue_yoy_growth=na_fact(),
        gross_margin=na_fact(),
        operating_margin=na_fact(),
        fcf=na_fact(),
        fcf_margin=na_fact(),
        net_debt=na_fact(),
        total_debt=na_fact(),
        cash=na_fact(),
        roe=na_fact(),
        roic=na_fact(),
        eps_ttm=na_fact(),
        forward_pe=na_fact(),
        trailing_pe=na_fact(),
        ev_to_ebitda=na_fact(),
        ev_to_revenue=na_fact(),
        price_to_book=na_fact(),
        peg_ratio=na_fact(),
        sector=None,
        industry=None,
    )


@pytest.fixture
def healthy_market():
    bars = [
        PriceBar(date=date(2026, 1, 1), open=100 + i * 0.1, high=101 + i * 0.1, low=99 + i * 0.1,
                  close=100 + i * 0.15, volume=1_000_000)
        for i in range(220)
    ]
    return MarketSnapshot(
        ticker="TEST",
        as_of=datetime.utcnow(),
        last_price=make_fact(bars[-1].close, period_date=date(2026, 8, 15)),
        price_history=bars,
        market_cap=make_fact(50_000_000_000),
        beta=make_fact(1.1),
        fifty_two_week_high=make_fact(140.0),
        fifty_two_week_low=make_fact(95.0),
    )
