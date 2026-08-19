import pytest

from joey_park.db.database import Database
from joey_park.memory.thesis_tracker import detect_thesis_change


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


def _save_result(db, ticker, overall_score, investment_view, analysis_date):
    db.upsert_stock(ticker, None, None, None)
    run_id = db.start_run(ticker, model="test", prompt_version="v0")
    result_id = db.save_analysis_result(
        {
            "run_id": run_id, "ticker": ticker, "analysis_date": analysis_date,
            "price_at_analysis": 100.0, "overall_score": overall_score,
            "investment_view": investment_view, "confidence": "Medium",
            "catalysts": [], "risks": [], "macro_risk_flags": {}, "data_quality_warnings": [],
            "raw_dimension_facts": {},
        }
    )
    db.save_thesis(
        {
            "ticker": ticker, "result_id": result_id, "recorded_at": analysis_date,
            "thesis_summary": "test thesis", "key_risks": [], "target_assumptions": {},
            "decision": investment_view, "change_vs_prior": "NEW", "change_reason": "",
        }
    )
    return result_id


def test_first_analysis_is_new(db):
    change = detect_thesis_change(db, "AAA", 0.7, "Bullish", "Medium", score_change_threshold=0.15)
    assert change.classification == "NEW"


def test_score_improvement_is_strengthened(db):
    _save_result(db, "AAA", 0.5, "Neutral", "2026-01-01T00:00:00")
    _save_result(db, "AAA", 0.5, "Neutral", "2026-02-01T00:00:00")  # this becomes "new" result being compared
    change = detect_thesis_change(db, "AAA", 0.75, "Bullish", "High", score_change_threshold=0.15)
    assert change.classification in ("STRENGTHENED",)


def test_view_flip_to_bearish_is_broken(db):
    _save_result(db, "BBB", 0.6, "Bullish", "2026-01-01T00:00:00")
    _save_result(db, "BBB", 0.6, "Bullish", "2026-02-01T00:00:00")
    change = detect_thesis_change(db, "BBB", 0.55, "Bearish", "Medium", score_change_threshold=0.15)
    assert change.classification == "BROKEN"


def test_small_move_is_unchanged(db):
    _save_result(db, "CCC", 0.5, "Neutral", "2026-01-01T00:00:00")
    _save_result(db, "CCC", 0.5, "Neutral", "2026-02-01T00:00:00")
    change = detect_thesis_change(db, "CCC", 0.52, "Neutral", "Medium", score_change_threshold=0.15)
    assert change.classification == "UNCHANGED"
