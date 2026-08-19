from datetime import date, datetime

from joey_park.data.models import DataStatus, Fact, MarketSnapshot, PriceBar, SourceTier
from joey_park.data.validation import run_data_quality_gate


def test_healthy_data_passes_gate(healthy_financials, healthy_market):
    report = run_data_quality_gate(
        "TEST", healthy_market, healthy_financials,
        price_staleness_days=3, fundamentals_staleness_days=100, min_completeness_pct=0.6,
    )
    assert report.completeness_pct == 1.0
    assert report.passed


def test_sparse_data_fails_completeness(sparse_financials, healthy_market):
    report = run_data_quality_gate(
        "THIN", healthy_market, sparse_financials,
        price_staleness_days=3, fundamentals_staleness_days=100, min_completeness_pct=0.6,
    )
    assert report.completeness_pct < 0.6
    assert not report.passed
    assert "completeness" in report.checks_run
    assert len(report.warnings) > 0


def test_stale_price_produces_warning(healthy_financials, healthy_market):
    healthy_market.last_price = Fact(
        value=100.0, source="test", tier=SourceTier.TIER_2_MARKET_DATA,
        period_date=date(2020, 1, 1), available_date=date(2020, 1, 1),
        retrieval_timestamp=datetime.utcnow(), status=DataStatus.OK,
    )
    report = run_data_quality_gate(
        "TEST", healthy_market, healthy_financials,
        price_staleness_days=3, fundamentals_staleness_days=100, min_completeness_pct=0.6,
    )
    assert any("일 전 데이터" in w for w in report.warnings)


def test_frozen_price_feed_detected(healthy_financials):
    bars = [
        PriceBar(date=date(2026, 1, i + 1), open=100, high=100, low=100, close=100.0, volume=1000)
        for i in range(25)
    ]
    frozen_market = MarketSnapshot(
        ticker="TEST", as_of=datetime.utcnow(),
        last_price=Fact(100.0, "test", SourceTier.TIER_2_MARKET_DATA, date.today(), date.today(), datetime.utcnow(), DataStatus.OK),
        price_history=bars,
    )
    report = run_data_quality_gate(
        "TEST", frozen_market, healthy_financials,
        price_staleness_days=3, fundamentals_staleness_days=100, min_completeness_pct=0.6,
    )
    assert any("동일" in w or "멈춰" in w for w in report.warnings)


def test_nonpositive_price_fails_gate(healthy_financials, healthy_market):
    healthy_market.last_price = Fact(
        value=-5.0, source="test", tier=SourceTier.TIER_2_MARKET_DATA,
        period_date=date.today(), available_date=date.today(),
        retrieval_timestamp=datetime.utcnow(), status=DataStatus.OK,
    )
    report = run_data_quality_gate(
        "TEST", healthy_market, healthy_financials,
        price_staleness_days=3, fundamentals_staleness_days=100, min_completeness_pct=0.6,
    )
    assert not report.passed
