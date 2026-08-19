"""Official SEC EDGAR data provider (Tier 1 — see docs/SOURCE_COMPARISON.md).

Free, no API key, but SEC's fair-access policy requires a real contact
identifier in the User-Agent header of every request
(https://www.sec.gov/os/webmaster-faq#code-support). Configure via
SEC_EDGAR_CONTACT_EMAIL in .env.

Unlike yfinance, EDGAR's XBRL company-facts API reports an exact `filed`
date per fact, so `available_date` here is measured, not estimated.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from joey_park.data.models import DataStatus, Fact, SourceTier

logger = logging.getLogger(__name__)

_BASE = "https://data.sec.gov"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_TIER = SourceTier.TIER_1_OFFICIAL
_CACHE_DIR = Path(__file__).resolve().parents[3] / ".cache"
_TICKER_MAP_CACHE = _CACHE_DIR / "sec_ticker_map.json"
_TICKER_MAP_TTL_SECONDS = 7 * 24 * 3600

# us-gaap XBRL concepts we care about, in priority order (first match wins),
# since companies use inconsistent tags across filings/industries.
_CONCEPT_CANDIDATES = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "net_income": ["NetIncomeLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": ["StockholdersEquity"],
}


class SecEdgarProvider:
    def __init__(self, contact_email: str):
        if not contact_email or contact_email == "your-email@example.com":
            logger.warning(
                "SEC_EDGAR_CONTACT_EMAIL is not configured — requests will use a "
                "placeholder User-Agent, which SEC may rate-limit or block."
            )
        self._headers = {
            "User-Agent": f"JoeyParkEquityAgent/0.1 ({contact_email})",
            "Accept-Encoding": "gzip, deflate",
        }
        self._session = requests.Session()
        self._session.headers.update(self._headers)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _get(self, url: str) -> dict:
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        time.sleep(0.11)  # stay under SEC's 10 req/sec fair-access limit
        return resp.json()

    def _ticker_to_cik(self, ticker: str) -> str | None:
        mapping = self._load_ticker_map()
        entry = mapping.get(ticker.upper())
        return f"{entry:010d}" if entry is not None else None

    def _load_ticker_map(self) -> dict[str, int]:
        if _TICKER_MAP_CACHE.exists():
            age = time.time() - _TICKER_MAP_CACHE.stat().st_mtime
            if age < _TICKER_MAP_TTL_SECONDS:
                with open(_TICKER_MAP_CACHE, encoding="utf-8") as f:
                    return json.load(f)

        try:
            raw = self._get(_TICKER_MAP_URL)
        except Exception as exc:
            logger.warning("Failed to fetch SEC ticker map: %s", exc)
            if _TICKER_MAP_CACHE.exists():
                with open(_TICKER_MAP_CACHE, encoding="utf-8") as f:
                    return json.load(f)
            return {}

        mapping = {row["ticker"].upper(): row["cik_str"] for row in raw.values()}
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_TICKER_MAP_CACHE, "w", encoding="utf-8") as f:
            json.dump(mapping, f)
        return mapping

    def fetch_company_facts(self, ticker: str) -> dict[str, Fact]:
        """Returns the latest value for each concept in _CONCEPT_CANDIDATES,
        each as a Fact with an exact SEC-filed `available_date`.
        """
        cik = self._ticker_to_cik(ticker)
        if cik is None:
            logger.info("No CIK found for ticker %s in SEC ticker map", ticker)
            return {k: Fact.unavailable("sec_edgar", _TIER) for k in _CONCEPT_CANDIDATES}

        try:
            facts_json = self._get(f"{_BASE}/api/xbrl/companyfacts/CIK{cik}.json")
        except Exception as exc:
            logger.warning("SEC companyfacts fetch failed for %s (CIK %s): %s", ticker, cik, exc)
            return {k: Fact.unavailable("sec_edgar", _TIER) for k in _CONCEPT_CANDIDATES}

        us_gaap = facts_json.get("facts", {}).get("us-gaap", {})
        results: dict[str, Fact] = {}
        for key, candidates in _CONCEPT_CANDIDATES.items():
            results[key] = self._extract_latest(us_gaap, candidates)
        return results

    @staticmethod
    def _extract_latest(us_gaap: dict, concept_candidates: list[str]) -> Fact:
        for concept in concept_candidates:
            node = us_gaap.get(concept)
            if not node:
                continue
            units = node.get("units", {})
            series = units.get("USD") or units.get("USD/shares") or next(iter(units.values()), [])
            # Prefer 10-Q/10-K annual/quarterly duration facts, most recently filed.
            candidates = [f for f in series if f.get("form") in ("10-Q", "10-K")]
            if not candidates:
                continue
            latest = max(candidates, key=lambda f: f.get("filed", ""))
            try:
                period_end = date.fromisoformat(latest["end"])
                filed = date.fromisoformat(latest["filed"])
            except (KeyError, ValueError):
                continue
            return Fact(
                value=latest.get("val"),
                source=f"sec_edgar:{concept}",
                tier=SourceTier.TIER_1_OFFICIAL,
                period_date=period_end,
                available_date=filed,
                retrieval_timestamp=datetime.now(timezone.utc),
                status=DataStatus.OK,
            )
        return Fact.unavailable("sec_edgar", SourceTier.TIER_1_OFFICIAL)

    def fetch_recent_filings(self, ticker: str, limit: int = 10) -> list[dict]:
        """Lightweight filing metadata (form, filed date, accession number) —
        used by the News & Catalyst agent as a Tier-1 event signal without
        pulling full filing text.
        """
        cik = self._ticker_to_cik(ticker)
        if cik is None:
            return []
        try:
            data = self._get(f"{_BASE}/submissions/CIK{cik}.json")
        except Exception as exc:
            logger.warning("SEC submissions fetch failed for %s: %s", ticker, exc)
            return []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        out = []
        for form, filed, accession in list(zip(forms, dates, accessions))[:limit]:
            out.append({"form": form, "filed": filed, "accession_number": accession})
        return out
