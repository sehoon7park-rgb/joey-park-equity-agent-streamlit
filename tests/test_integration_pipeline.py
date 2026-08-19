"""End-to-end pipeline test: Ticker -> ... -> Report, with data and LLM
providers mocked so the test is fast, deterministic, and network-free.
"""
import json

import pytest

from joey_park.agents.data_agent import DataBundle
from joey_park.agents.orchestrator import Orchestrator
from joey_park.config.settings import load_settings
from joey_park.db.database import Database
from joey_park.llm.base import LLMProvider, LLMResponse

_FAKE_LLM_JSON = {
    # Research fields
    "business_summary": "Test Co sells widgets.",
    "growth_drivers": ["driver 1"],
    "quality_notes": "solid margins",
    "competitive_position": "moderate moat",
    "catalysts": [{"description": "new product", "grounded_in": "sec filing"}],
    "data_gaps": [],
    # Critic fields
    "numbers_match_facts": True,
    "bull_only_bias_detected": False,
    "missing_bear_case": False,
    "valuation_assumptions_reasonable": True,
    "data_gaps_acknowledged": True,
    "contradictions": [],
    "issues": [],
    "verdict": "PASS",
    # Decision fields
    "investment_view": "Bullish",
    "confidence": "Medium",
    "time_horizon": "Medium",
    "thesis": "Test Co looks attractive at current levels.",
    "bull_case": {"narrative": "Growth accelerates", "probability": 0.4},
    "base_case": {"narrative": "Growth in line", "probability": 0.4},
    "bear_case": {"narrative": "Margins compress", "probability": 0.2},
    "valuation_summary": "Reasonably priced given growth.",
    "what_would_change_my_mind": "Revenue growth drops below 10% YoY for two consecutive quarters.",
}


class FakeLLMProvider(LLMProvider):
    def __init__(self, configured=True, raise_error=False):
        self._configured = configured
        self._raise_error = raise_error
        self.call_count = 0

    def is_configured(self):
        return self._configured

    def complete(self, *, system, prompt, max_tokens=2000):
        self.call_count += 1
        if self._raise_error:
            raise RuntimeError("simulated LLM provider outage")
        return LLMResponse(text=json.dumps(_FAKE_LLM_JSON), input_tokens=100, output_tokens=100, model="fake")


class FakeDataAgent:
    def __init__(self, financials, market):
        self._financials = financials
        self._market = market

    def fetch(self, ticker):
        return DataBundle(
            ticker=ticker,
            market=self._market,
            financials=self._financials,
            sec_facts={},
            sec_recent_filings=[{"form": "10-Q", "filed": "2026-07-01", "accession_number": "0001"}],
            macro_facts={},
            sources_used=["fake_data_agent"],
            errors=[],
        )


@pytest.fixture
def settings():
    return load_settings()


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


def test_full_pipeline_produces_structured_report(settings, db, healthy_financials, healthy_market):
    data_agent = FakeDataAgent(healthy_financials, healthy_market)
    llm = FakeLLMProvider(configured=True)
    orchestrator = Orchestrator(settings, db, data_agent, llm)

    report = orchestrator.analyze("test")

    assert report.ticker == "TEST"
    assert report.overall_score is not None
    assert 0.0 <= report.overall_score <= 1.0
    assert report.decision.investment_view == "Bullish"
    assert report.decision.confidence == "Medium"
    assert report.thesis_change.classification == "NEW"
    assert llm.call_count == 3  # research + critic + decision

    saved = db.get_latest_result("TEST")
    assert saved is not None
    assert saved["investment_view"] == "Bullish"


def test_second_run_detects_thesis_continuity(settings, db, healthy_financials, healthy_market):
    data_agent = FakeDataAgent(healthy_financials, healthy_market)
    llm = FakeLLMProvider(configured=True)
    orchestrator = Orchestrator(settings, db, data_agent, llm)

    orchestrator.analyze("test")
    second = orchestrator.analyze("test")

    assert second.thesis_change.classification == "UNCHANGED"  # same fake data -> same score both times


def test_llm_not_configured_degrades_without_crashing(settings, db, healthy_financials, healthy_market):
    data_agent = FakeDataAgent(healthy_financials, healthy_market)
    llm = FakeLLMProvider(configured=False)
    orchestrator = Orchestrator(settings, db, data_agent, llm)

    report = orchestrator.analyze("test")

    assert report.decision.investment_view == "Neutral"
    assert report.decision.confidence == "Low"
    assert "DATA_NOT_AVAILABLE" in report.decision.thesis
    # quant scores still compute even with no LLM
    assert report.dimension_scores["fundamental"] is not None


def test_llm_provider_outage_degrades_without_crashing(settings, db, healthy_financials, healthy_market):
    data_agent = FakeDataAgent(healthy_financials, healthy_market)
    llm = FakeLLMProvider(configured=True, raise_error=True)
    orchestrator = Orchestrator(settings, db, data_agent, llm)

    report = orchestrator.analyze("test")  # must not raise

    assert report.decision.investment_view == "Neutral"
    assert "LLM call failed" in report.decision.thesis or "DATA_NOT_AVAILABLE" in report.decision.thesis
    assert report.research.business_summary.startswith("DATA_NOT_AVAILABLE")


def test_sparse_data_still_produces_a_report(settings, db, sparse_financials, healthy_market):
    data_agent = FakeDataAgent(sparse_financials, healthy_market)
    llm = FakeLLMProvider(configured=True)
    orchestrator = Orchestrator(settings, db, data_agent, llm)

    report = orchestrator.analyze("thin")  # must not raise despite mostly-missing fundamentals

    assert report.ticker == "THIN"
    assert report.completeness_pct < 1.0
