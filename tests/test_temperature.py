from datetime import date, datetime, timedelta

from joey_park.analytics.temperature import compute_temperature
from joey_park.data.models import DataStatus, Fact, MarketSnapshot, PriceBar, SourceTier


def _market_with_bars(bars: list[PriceBar]) -> MarketSnapshot:
    return MarketSnapshot(
        ticker="TEST",
        as_of=datetime.utcnow(),
        last_price=Fact(bars[-1].close, "test", SourceTier.TIER_2_MARKET_DATA, date.today(), date.today(), datetime.utcnow(), DataStatus.OK) if bars else Fact.unavailable("test", SourceTier.TIER_2_MARKET_DATA),
        price_history=bars,
    )


def test_insufficient_history_returns_data_not_available():
    bars = [PriceBar(date=date(2026, 1, i + 1), open=1, high=1, low=1, close=100.0, volume=1000) for i in range(10)]
    result = compute_temperature(_market_with_bars(bars))
    assert result.temperature is None
    assert result.label == "DATA_NOT_AVAILABLE"


def test_stable_flat_series_has_low_temperature():
    bars = [
        PriceBar(date=date(2026, 1, 1), open=100, high=100, low=100, close=100.0 + (i % 3) * 0.01, volume=1_000_000)
        for i in range(100)
    ]
    result = compute_temperature(_market_with_bars(bars))
    assert result.temperature is not None
    assert result.label in ("평상시", "주의")  # near-flat/quiet series shouldn't read as "고온"


def test_recent_spike_raises_temperature():
    base = date(2026, 1, 1)
    bars = [
        PriceBar(date=base + timedelta(days=i), open=100, high=100, low=100, close=100.0, volume=1_000_000)
        for i in range(90)
    ]
    # Sharp recent volume + price spike in the last 10 bars
    for i in range(90, 100):
        bars.append(
            PriceBar(date=base + timedelta(days=i), open=100, high=150, low=100, close=100.0 + (i - 89) * 5, volume=10_000_000)
        )
    result = compute_temperature(_market_with_bars(bars))
    assert result.temperature is not None
    assert result.temperature > 1.0


def test_temperature_components_present_when_computed():
    base = date(2026, 1, 1)
    bars = [
        PriceBar(date=base + timedelta(days=i), open=100, high=101, low=99, close=100.0 + (i % 5), volume=1_000_000 + i * 1000)
        for i in range(80)
    ]
    result = compute_temperature(_market_with_bars(bars))
    assert result.z_return is not None
    assert result.z_volume is not None
    assert result.z_volatility is not None
