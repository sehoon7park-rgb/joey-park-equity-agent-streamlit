"""Deterministic dimension scoring — no LLM calls in this module.

Per docs/DECISION_LOG.md D1/D4: every number here is computed from fetched
Facts. Where a Fact is DATA_NOT_AVAILABLE, the corresponding sub-score is
None (not guessed, not defaulted to a neutral value silently) and
`combine_scores` renormalizes weights over whatever is actually available,
lowering confidence rather than lowering the score.
"""
from __future__ import annotations

from dataclasses import dataclass

from joey_park.data.models import DataStatus, Fact, FinancialSnapshot, MarketSnapshot


def _val(fact: Fact | None) -> float | None:
    if fact is None or fact.status != DataStatus.OK:
        return None
    return fact.value


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _linear_score(value: float, low: float, high: float) -> float:
    """Maps value in [low, high] to [0, 1], clamped. Handles low > high (inverted)."""
    if low == high:
        return 0.5
    return _clamp01((value - low) / (high - low))


@dataclass
class DimensionScores:
    fundamental: float | None
    growth: float | None
    quality: float | None
    valuation: float | None
    momentum: float | None
    cycle_position: float | None
    catalyst: float | None
    cycle_lept: dict[str, float | None] | None = None  # raw L/E/P/T for transparency


def score_fundamental(fin: FinancialSnapshot) -> float | None:
    margins = [_val(fin.gross_margin), _val(fin.operating_margin), _val(fin.fcf_margin)]
    available = [m for m in margins if m is not None]
    if not available:
        return None
    # Gross margin 0-80%+, operating margin 0-40%+, FCF margin 0-30%+ are strong.
    weighted = 0.0
    weight_total = 0.0
    if _val(fin.gross_margin) is not None:
        weighted += _linear_score(_val(fin.gross_margin), 0.0, 0.80) * 0.3
        weight_total += 0.3
    if _val(fin.operating_margin) is not None:
        weighted += _linear_score(_val(fin.operating_margin), -0.10, 0.40) * 0.4
        weight_total += 0.4
    if _val(fin.fcf_margin) is not None:
        weighted += _linear_score(_val(fin.fcf_margin), -0.10, 0.30) * 0.3
        weight_total += 0.3
    return weighted / weight_total if weight_total else None


def score_growth(fin: FinancialSnapshot) -> float | None:
    growth = _val(fin.revenue_yoy_growth)
    if growth is None:
        return None
    # 0% growth -> 0.2 (still a going concern), 40%+ YoY -> 1.0
    return _linear_score(growth, -0.10, 0.40)


def score_quality(fin: FinancialSnapshot) -> float | None:
    roe = _val(fin.roe)
    net_debt = _val(fin.net_debt)
    revenue = _val(fin.revenue)
    parts = []
    if roe is not None:
        parts.append((_linear_score(roe, 0.0, 0.30), 0.6))
    if net_debt is not None and revenue not in (None, 0):
        leverage = net_debt / revenue
        # negative net debt (net cash) -> best; leverage > 2x revenue -> worst
        parts.append((_linear_score(-leverage, -2.0, 1.0), 0.4))
    if not parts:
        return None
    weight_total = sum(w for _, w in parts)
    return sum(s * w for s, w in parts) / weight_total


def score_valuation(fin: FinancialSnapshot, market: MarketSnapshot, heuristics: dict) -> float | None:
    parts = []
    peg = _val(fin.peg_ratio)
    if peg is not None and peg > 0:
        # lower PEG = cheaper = higher score
        parts.append((_linear_score(-peg, -heuristics["peg_expensive_above"], -heuristics["peg_cheap_below"]), 0.4))
    ev_ebitda = _val(fin.ev_to_ebitda)
    if ev_ebitda is not None and ev_ebitda > 0:
        parts.append(
            (_linear_score(-ev_ebitda, -heuristics["ev_ebitda_expensive_above"], -heuristics["ev_ebitda_cheap_below"]), 0.3)
        )
    fcf = _val(fin.fcf)
    market_cap = _val(market.market_cap)
    if fcf is not None and market_cap not in (None, 0):
        fcf_yield = fcf / market_cap
        parts.append(
            (_linear_score(fcf_yield, heuristics["fcf_yield_poor_below"], heuristics["fcf_yield_good_above"]), 0.3)
        )
    if not parts:
        return None
    weight_total = sum(w for _, w in parts)
    return sum(s * w for s, w in parts) / weight_total


def score_momentum(market: MarketSnapshot) -> float | None:
    if len(market.price_history) < 60:
        return None
    closes = [bar.close for bar in market.price_history]
    last = closes[-1]
    ma50 = sum(closes[-50:]) / 50
    ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None

    high52 = _val(market.fifty_two_week_high)
    low52 = _val(market.fifty_two_week_low)

    parts = []
    parts.append((_linear_score((last - ma50) / ma50, -0.15, 0.15), 0.4))
    if ma200:
        parts.append((_linear_score((last - ma200) / ma200, -0.20, 0.20), 0.3))
    if high52 and low52 and high52 != low52:
        position_in_range = (last - low52) / (high52 - low52)
        parts.append((_clamp01(position_in_range), 0.3))
    if not parts:
        return None
    weight_total = sum(w for _, w in parts)
    return sum(s * w for s, w in parts) / weight_total


def score_cycle_position(fin: FinancialSnapshot, topology_weight: float | None) -> tuple[float | None, dict]:
    """L x (1-E) x P x T, computed from data instead of LLM-estimated
    (docs/DECISION_LOG.md D1). T comes from config (see sector_universe.yaml)
    since structural/monopoly position isn't derivable from a financial
    statement.
    """
    growth = _val(fin.revenue_yoy_growth)
    net_debt = _val(fin.net_debt)
    revenue = _val(fin.revenue)
    forward_pe = _val(fin.forward_pe)
    trailing_pe = _val(fin.trailing_pe)

    L = _linear_score(growth, -0.10, 0.40) if growth is not None else None

    E = None
    if net_debt is not None and revenue not in (None, 0):
        leverage = net_debt / revenue
        E = 1 - _linear_score(-leverage, -2.0, 1.0)  # higher leverage -> higher risk

    P = None
    if forward_pe is not None and trailing_pe not in (None, 0) and forward_pe > 0:
        # forward PE below trailing PE implies expected earnings growth not yet
        # fully re-rated -> more room, i.e. cheaper relative to its own trajectory.
        re_rating = (trailing_pe - forward_pe) / trailing_pe
        P = _linear_score(re_rating, -0.30, 0.30)

    T = topology_weight

    raw = {"L": L, "E": E, "P": P, "T": T}
    present = [v for v in (L, E, P, T) if v is not None]
    if len(present) < 3:  # need at least 3 of 4 inputs to trust the composite
        return None, raw

    l_ = L if L is not None else 0.5
    e_ = E if E is not None else 0.3
    p_ = P if P is not None else 0.5
    t_ = T if T is not None else 0.4
    score = l_ * (1 - e_) * p_ * t_
    return _clamp01(score / 0.5), raw  # /0.5 rescales typical range back toward [0,1]


def combine_scores(
    dimension_scores: dict[str, float | None],
    weights: dict[str, float],
) -> tuple[float | None, float]:
    """Weighted average over available (non-None) dimension scores, with
    weights renormalized to sum to 1 over what's actually present.
    Returns (overall_score, completeness_fraction).
    """
    available = {k: v for k, v in dimension_scores.items() if v is not None}
    completeness = len(available) / len(dimension_scores) if dimension_scores else 0.0
    if not available:
        return None, 0.0
    weight_sum = sum(weights[k] for k in available)
    if weight_sum == 0:
        return None, completeness
    overall = sum(available[k] * weights[k] for k in available) / weight_sum
    return _clamp01(overall), completeness
