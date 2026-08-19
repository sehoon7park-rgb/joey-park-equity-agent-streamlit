"""Multi-method valuation summary (master-spec section 24: don't force one
method on every company). This module produces a structured, human-readable
verdict per method — the *scoring* of valuation lives in scoring.py; this
module is what the report/narrative actually quotes.
"""
from __future__ import annotations

from dataclasses import dataclass

from joey_park.data.models import DataStatus, Fact, FinancialSnapshot, MarketSnapshot


@dataclass
class ValuationVerdict:
    method: str
    value: float | None
    verdict: str  # CHEAP/FAIR/EXPENSIVE/DATA_NOT_AVAILABLE
    note: str


def _val(fact: Fact | None) -> float | None:
    if fact is None or fact.status != DataStatus.OK:
        return None
    return fact.value


def _band_verdict(value: float | None, cheap_below: float, expensive_above: float, higher_is_cheaper: bool = False) -> str:
    if value is None:
        return "DATA_NOT_AVAILABLE"
    if higher_is_cheaper:
        if value >= expensive_above:
            return "CHEAP"
        if value <= cheap_below:
            return "EXPENSIVE"
        return "FAIR"
    if value <= cheap_below:
        return "CHEAP"
    if value >= expensive_above:
        return "EXPENSIVE"
    return "FAIR"


def evaluate(
    fin: FinancialSnapshot,
    market: MarketSnapshot,
    sector: str | None,
    methods_by_sector: dict[str, list[str]],
    heuristics: dict,
) -> list[ValuationVerdict]:
    sector_key = (sector or "default").lower().replace(" ", "_")
    methods = methods_by_sector.get(sector_key, methods_by_sector["default"])

    results: list[ValuationVerdict] = []
    for method in methods:
        if method == "pe_multiple":
            v = _val(fin.trailing_pe)
            results.append(
                ValuationVerdict(
                    "pe_multiple", v,
                    _band_verdict(v, 15, 30),
                    "Trailing P/E vs. a generic 15x/30x reasonableness band (no live peer set in MVP).",
                )
            )
        elif method == "ev_ebitda":
            v = _val(fin.ev_to_ebitda)
            results.append(
                ValuationVerdict(
                    "ev_ebitda", v,
                    _band_verdict(v, heuristics["ev_ebitda_cheap_below"], heuristics["ev_ebitda_expensive_above"]),
                    "EV/EBITDA vs. configured cheap/expensive thresholds (config.yaml valuation.heuristics).",
                )
            )
        elif method == "ev_revenue":
            v = _val(fin.ev_to_revenue)
            results.append(
                ValuationVerdict(
                    "ev_revenue", v,
                    _band_verdict(v, 4, 15),
                    "EV/Revenue vs. a generic high-growth-software reasonableness band.",
                )
            )
        elif method == "fcf_yield":
            fcf = _val(fin.fcf)
            mc = _val(market.market_cap)
            v = fcf / mc if (fcf is not None and mc) else None
            results.append(
                ValuationVerdict(
                    "fcf_yield", v,
                    _band_verdict(v, heuristics["fcf_yield_poor_below"], heuristics["fcf_yield_good_above"], higher_is_cheaper=True),
                    "Free cash flow / market cap; higher yield = cheaper.",
                )
            )
        elif method == "peg":
            v = _val(fin.peg_ratio)
            results.append(
                ValuationVerdict(
                    "peg", v,
                    _band_verdict(v, heuristics["peg_cheap_below"], heuristics["peg_expensive_above"]),
                    "P/E relative to growth rate; <1 historically considered cheap, >2.5 expensive.",
                )
            )
        elif method == "price_to_book":
            v = _val(fin.price_to_book)
            results.append(
                ValuationVerdict(
                    "price_to_book", v,
                    _band_verdict(v, 1.0, 3.0),
                    "Price/Book vs. a generic financials-sector reasonableness band.",
                )
            )
        else:
            results.append(
                ValuationVerdict(method, None, "DATA_NOT_AVAILABLE", f"Method '{method}' not implemented in MVP.")
            )
    return results
