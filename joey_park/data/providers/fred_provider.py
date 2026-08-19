"""Optional macro data provider (FRED — Federal Reserve Economic Data).

Free but requires a key (docs/DECISION_LOG.md D9). If FRED_API_KEY is unset,
MacroAgent should catch the resulting DATA_NOT_AVAILABLE facts and degrade
gracefully rather than failing the whole pipeline.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from joey_park.data.models import DataStatus, Fact, SourceTier

logger = logging.getLogger(__name__)

_BASE = "https://api.stlouisfed.org/fred/series/observations"
_TIER = SourceTier.TIER_2_MARKET_DATA

# FRED series IDs for the macro signals the Macro Agent cares about.
SERIES = {
    "fed_funds_rate": "FEDFUNDS",
    "10y_treasury_yield": "DGS10",
    "high_yield_credit_spread": "BAMLH0A0HYM2",
    "cpi_yoy": "CPIAUCSL",
}


class FredProvider:
    def __init__(self, api_key: str | None):
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _get(self, series_id: str) -> dict:
        params = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }
        resp = requests.get(_BASE, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def fetch_latest(self, series_key: str) -> Fact:
        if not self.is_configured():
            return Fact.unavailable("fred", _TIER)
        series_id = SERIES.get(series_key)
        if series_id is None:
            raise ValueError(f"Unknown FRED series key: {series_key}")
        try:
            payload = self._get(series_id)
            obs = payload["observations"][0]
            if obs["value"] == ".":
                return Fact.unavailable("fred", _TIER)
            period = date.fromisoformat(obs["date"])
            return Fact(
                value=float(obs["value"]),
                source=f"fred:{series_id}",
                tier=_TIER,
                period_date=period,
                available_date=period,
                retrieval_timestamp=datetime.now(timezone.utc),
                status=DataStatus.OK,
            )
        except Exception as exc:
            logger.warning("FRED fetch failed for %s: %s", series_key, exc)
            return Fact.unavailable("fred", _TIER)

    def fetch_all(self) -> dict[str, Fact]:
        return {key: self.fetch_latest(key) for key in SERIES}
