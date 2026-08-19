import pytest

from joey_park.agents.portfolio_agent import PortfolioAgent
from joey_park.agents.risk_agent import RiskAgent
from joey_park.db.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


def test_add_and_close_position(db):
    db.upsert_stock("AAA", None, "semiconductor", None)
    position_id = db.add_position("AAA", 10, 100.0, "test note")

    open_positions = db.get_open_positions()
    assert len(open_positions) == 1
    assert open_positions[0]["ticker"] == "AAA"
    assert open_positions[0]["shares"] == 10

    db.close_position(position_id)
    assert db.get_open_positions() == []


def test_get_stock_returns_sector(db):
    db.upsert_stock("BBB", "Big Bank Inc", "financial", "Banks")
    row = db.get_stock("BBB")
    assert row["sector"] == "financial"


def test_get_stock_missing_returns_none(db):
    assert db.get_stock("NOPE") is None


def test_portfolio_agent_flags_single_position_concentration():
    agent = PortfolioAgent(RiskAgent(), max_single_position_pct=0.15, max_sector_pct=0.35)
    positions = [
        {"ticker": "AAA", "market_value": 9000, "sector": "semiconductor"},
        {"ticker": "BBB", "market_value": 1000, "sector": "ai_software_cloud"},
    ]
    summary = agent.summarize(positions)
    assert summary.total_market_value == 10000
    assert any(w.kind == "position" and w.label == "AAA" for w in summary.concentration_warnings)


def test_portfolio_agent_flags_sector_concentration():
    agent = PortfolioAgent(RiskAgent(), max_single_position_pct=0.5, max_sector_pct=0.35)
    positions = [
        {"ticker": "AAA", "market_value": 4000, "sector": "semiconductor"},
        {"ticker": "BBB", "market_value": 4000, "sector": "semiconductor"},
        {"ticker": "CCC", "market_value": 2000, "sector": "value_anchors"},
    ]
    summary = agent.summarize(positions)
    assert any(w.kind == "sector" and w.label == "semiconductor" for w in summary.concentration_warnings)


def test_portfolio_agent_no_warnings_when_diversified():
    agent = PortfolioAgent(RiskAgent(), max_single_position_pct=0.5, max_sector_pct=0.5)
    positions = [
        {"ticker": "AAA", "market_value": 5000, "sector": "semiconductor"},
        {"ticker": "BBB", "market_value": 5000, "sector": "ai_software_cloud"},
    ]
    summary = agent.summarize(positions)
    assert summary.concentration_warnings == []
