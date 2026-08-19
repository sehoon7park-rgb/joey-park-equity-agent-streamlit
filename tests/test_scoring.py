from joey_park.analytics.scoring import (
    combine_scores,
    score_fundamental,
    score_growth,
    score_momentum,
    score_quality,
    score_valuation,
)


def test_score_growth_missing_data_returns_none(sparse_financials):
    assert score_growth(sparse_financials) is None


def test_score_growth_high_growth_scores_high(healthy_financials):
    score = score_growth(healthy_financials)
    assert score is not None
    assert 0.5 < score <= 1.0


def test_score_fundamental_within_bounds(healthy_financials):
    score = score_fundamental(healthy_financials)
    assert score is not None
    assert 0.0 <= score <= 1.0


def test_score_quality_rewards_net_cash_and_roe(healthy_financials):
    score = score_quality(healthy_financials)
    assert score is not None
    assert score > 0.5


def test_score_valuation_missing_data_returns_none(sparse_financials, healthy_market):
    heuristics = {
        "peg_cheap_below": 1.0, "peg_expensive_above": 2.5,
        "ev_ebitda_cheap_below": 10.0, "ev_ebitda_expensive_above": 25.0,
        "fcf_yield_good_above": 0.04, "fcf_yield_poor_below": 0.01,
    }
    assert score_valuation(sparse_financials, healthy_market, heuristics) is None


def test_score_momentum_requires_price_history(sparse_financials, healthy_market):
    from joey_park.data.models import MarketSnapshot
    from datetime import datetime
    from joey_park.data.models import Fact, SourceTier

    empty_market = MarketSnapshot(
        ticker="THIN", as_of=datetime.utcnow(),
        last_price=Fact.unavailable("test", SourceTier.TIER_2_MARKET_DATA),
    )
    assert score_momentum(empty_market) is None
    assert score_momentum(healthy_market) is not None


def test_combine_scores_renormalizes_over_available_dimensions():
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    scores = {"a": 1.0, "b": None, "c": None}
    overall, completeness = combine_scores(scores, weights)
    assert overall == 1.0  # only 'a' available -> renormalized weight is 100%
    assert completeness == 1 / 3


def test_combine_scores_all_missing_returns_none():
    overall, completeness = combine_scores({"a": None, "b": None}, {"a": 0.5, "b": 0.5})
    assert overall is None
    assert completeness == 0.0


def test_combine_scores_output_always_in_bounds():
    weights = {"a": 0.5, "b": 0.5}
    overall, _ = combine_scores({"a": 1.0, "b": 1.0}, weights)
    assert 0.0 <= overall <= 1.0
