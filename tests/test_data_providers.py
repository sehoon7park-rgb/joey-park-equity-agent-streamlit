"""Provider tests with network calls mocked out — no real API calls."""
import pandas as pd
import pytest

from joey_park.data.models import DataStatus
from joey_park.data.providers.sec_edgar_provider import SecEdgarProvider
from joey_park.data.providers.yfinance_provider import YFinanceProvider


class _FakeYfTicker:
    def __init__(self, info=None, raise_on_info=False, raise_on_history=False):
        self._info = info or {}
        self._raise_on_info = raise_on_info
        self._raise_on_history = raise_on_history

    @property
    def info(self):
        if self._raise_on_info:
            raise RuntimeError("simulated yfinance outage")
        return self._info

    def history(self, period="400d", auto_adjust=False):
        if self._raise_on_history:
            raise RuntimeError("simulated yfinance outage")
        idx = pd.date_range("2026-01-01", periods=5, freq="D")
        return pd.DataFrame(
            {"Open": [1, 2, 3, 4, 5], "High": [1, 2, 3, 4, 5], "Low": [1, 2, 3, 4, 5],
             "Close": [1.0, 2.0, 3.0, 4.0, 5.0], "Volume": [100, 100, 100, 100, 100],
             "Adj Close": [1.0, 2.0, 3.0, 4.0, 5.0]},
            index=idx,
        )

    @property
    def quarterly_financials(self):
        return pd.DataFrame()

    @property
    def quarterly_cashflow(self):
        return pd.DataFrame()

    @property
    def quarterly_balance_sheet(self):
        return pd.DataFrame()


def test_yfinance_market_snapshot_happy_path(monkeypatch):
    provider = YFinanceProvider()
    fake = _FakeYfTicker(info={"marketCap": 1000, "beta": 1.2, "fiftyTwoWeekHigh": 10, "fiftyTwoWeekLow": 1})
    monkeypatch.setattr("joey_park.data.providers.yfinance_provider._fetch_ticker", lambda t: fake)

    snapshot = provider.fetch_market_snapshot("TEST")

    assert snapshot.last_price.status == DataStatus.OK
    assert snapshot.last_price.value == 5.0
    assert snapshot.market_cap.value == 1000
    assert len(snapshot.price_history) == 5


def test_yfinance_market_snapshot_degrades_on_info_failure(monkeypatch):
    provider = YFinanceProvider()
    fake = _FakeYfTicker(raise_on_info=True)
    monkeypatch.setattr("joey_park.data.providers.yfinance_provider._fetch_ticker", lambda t: fake)

    snapshot = provider.fetch_market_snapshot("TEST")  # must not raise

    assert snapshot.market_cap.status == DataStatus.DATA_NOT_AVAILABLE
    assert snapshot.last_price.status == DataStatus.OK  # history still worked


def test_yfinance_market_snapshot_degrades_on_history_failure(monkeypatch):
    provider = YFinanceProvider()
    fake = _FakeYfTicker(info={"marketCap": 1000}, raise_on_history=True)
    monkeypatch.setattr("joey_park.data.providers.yfinance_provider._fetch_ticker", lambda t: fake)

    snapshot = provider.fetch_market_snapshot("TEST")  # must not raise

    assert snapshot.last_price.status == DataStatus.DATA_NOT_AVAILABLE
    assert snapshot.market_cap.status == DataStatus.OK


def test_sec_edgar_unknown_ticker_returns_unavailable_facts(monkeypatch):
    provider = SecEdgarProvider("test@example.com")
    monkeypatch.setattr(provider, "_load_ticker_map", lambda: {})

    facts = provider.fetch_company_facts("NOPE")

    assert all(f.status == DataStatus.DATA_NOT_AVAILABLE for f in facts.values())


def test_sec_edgar_extract_latest_picks_most_recently_filed():
    us_gaap = {
        "Revenues": {
            "units": {
                "USD": [
                    {"end": "2025-12-31", "filed": "2026-02-01", "val": 100, "form": "10-K"},
                    {"end": "2026-03-31", "filed": "2026-05-01", "val": 120, "form": "10-Q"},
                ]
            }
        }
    }
    fact = SecEdgarProvider._extract_latest(us_gaap, ["Revenues"])
    assert fact.value == 120
    assert fact.available_date.isoformat() == "2026-05-01"


def test_sec_edgar_facts_fetch_degrades_on_http_failure(monkeypatch):
    provider = SecEdgarProvider("test@example.com")
    monkeypatch.setattr(provider, "_ticker_to_cik", lambda t: "0000000001")

    def _boom(url):
        raise RuntimeError("simulated SEC outage")

    monkeypatch.setattr(provider, "_get", _boom)
    facts = provider.fetch_company_facts("TEST")  # must not raise
    assert all(f.status == DataStatus.DATA_NOT_AVAILABLE for f in facts.values())
