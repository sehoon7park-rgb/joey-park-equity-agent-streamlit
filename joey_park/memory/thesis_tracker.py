"""Thesis change detection — master-spec section 19.

Before writing a fresh narrative, every re-analysis first asks "what changed
since last time?" rather than starting from a blank page. This module is
pure comparison logic; it does not call the LLM.
"""
from __future__ import annotations

from dataclasses import dataclass

from joey_park.db.database import Database

_VIEW_POLARITY = {"Bullish": 1, "Neutral": 0, "Bearish": -1}


@dataclass
class ThesisChange:
    classification: str  # NEW/STRENGTHENED/UNCHANGED/WEAKENED/BROKEN
    reason: str
    prior_score: float | None
    new_score: float
    prior_view: str | None
    new_view: str


def detect_thesis_change(
    db: Database,
    ticker: str,
    new_overall_score: float,
    new_investment_view: str,
    new_confidence: str,
    score_change_threshold: float,
) -> ThesisChange:
    history = db.get_thesis_history(ticker, limit=1)
    if not history:
        return ThesisChange(
            classification="NEW",
            reason="No prior thesis on record for this ticker.",
            prior_score=None,
            new_score=new_overall_score,
            prior_view=None,
            new_view=new_investment_view,
        )

    prior = history[0]
    prior_result = db.get_result_history(ticker, limit=2)
    prior_score = None
    prior_view = None
    if len(prior_result) >= 2:
        # index 0 is the just-saved new result; index 1 is the true prior one
        prior_row = prior_result[1]
        prior_score = prior_row["overall_score"]
        prior_view = prior_row["investment_view"]

    if prior_score is None:
        return ThesisChange(
            classification="NEW",
            reason="Prior thesis record found but no comparable prior score.",
            prior_score=None,
            new_score=new_overall_score,
            prior_view=prior_view,
            new_view=new_investment_view,
        )

    score_delta = new_overall_score - prior_score
    view_flipped_negative = (
        _VIEW_POLARITY.get(prior_view, 0) >= 0 and _VIEW_POLARITY.get(new_investment_view, 0) < 0
    )
    view_flipped_positive = (
        _VIEW_POLARITY.get(prior_view, 0) <= 0 and _VIEW_POLARITY.get(new_investment_view, 0) > 0
    )

    if view_flipped_negative or (score_delta <= -score_change_threshold * 2 and new_confidence != "Low"):
        return ThesisChange(
            classification="BROKEN",
            reason=(
                f"Investment view flipped {prior_view} -> {new_investment_view}"
                if view_flipped_negative
                else f"Score dropped sharply ({prior_score:.2f} -> {new_overall_score:.2f})."
            ),
            prior_score=prior_score,
            new_score=new_overall_score,
            prior_view=prior_view,
            new_view=new_investment_view,
        )
    if view_flipped_positive or score_delta >= score_change_threshold:
        return ThesisChange(
            classification="STRENGTHENED",
            reason=f"Score improved {prior_score:.2f} -> {new_overall_score:.2f} (view: {prior_view} -> {new_investment_view}).",
            prior_score=prior_score,
            new_score=new_overall_score,
            prior_view=prior_view,
            new_view=new_investment_view,
        )
    if score_delta <= -score_change_threshold:
        return ThesisChange(
            classification="WEAKENED",
            reason=f"Score declined {prior_score:.2f} -> {new_overall_score:.2f}.",
            prior_score=prior_score,
            new_score=new_overall_score,
            prior_view=prior_view,
            new_view=new_investment_view,
        )
    return ThesisChange(
        classification="UNCHANGED",
        reason=f"Score moved only {score_delta:+.2f}, below the {score_change_threshold:.2f} threshold.",
        prior_score=prior_score,
        new_score=new_overall_score,
        prior_view=prior_view,
        new_view=new_investment_view,
    )
