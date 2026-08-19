"""Macro Agent — surfaces macro facts and computes the Type A/B/C risk
taxonomy carried from the source docs (docs/SOURCE_COMPARISON.md).

Type C (credit-spread-driven capex risk) is the only leg computable from a
free data source (FRED high-yield spread + company leverage), so it gets a
real flag. Type A (aggregate hyperscaler capex direction) and Type B
(margin compression from yield-parity/in-housing) require industry-wide
signals no free API provides — this agent surfaces the raw facts it does
have and marks those two flags LOW_CONFIDENCE / DATA_NOT_AVAILABLE rather
than guessing; the Research/Critic agents are expected to reason over
whatever qualitative catalyst/news facts exist instead of this agent
inventing a verdict.
"""
from __future__ import annotations

from dataclasses import dataclass

from joey_park.data.models import DataStatus, Fact, FinancialSnapshot


@dataclass
class MacroRiskFlags:
    type_a: str  # "FLAGGED" / "NOT_FLAGGED" / "DATA_NOT_AVAILABLE"
    type_b: str
    type_c: str
    notes: list[str]


@dataclass
class MacroResult:
    facts: dict
    risk_flags: MacroRiskFlags


_TYPE_C_SPREAD_THRESHOLD_BPS = 500  # high-yield OAS above this = elevated credit stress
_TYPE_C_LEVERAGE_THRESHOLD = 1.0  # net_debt / revenue


class MacroAgent:
    def run(self, macro_facts: dict[str, Fact], financials: FinancialSnapshot) -> MacroResult:
        notes: list[str] = []

        spread_fact = macro_facts.get("high_yield_credit_spread")
        spread_ok = spread_fact is not None and spread_fact.status == DataStatus.OK
        leverage = None
        if financials.net_debt.status == DataStatus.OK and financials.revenue.status == DataStatus.OK and financials.revenue.value:
            leverage = financials.net_debt.value / financials.revenue.value

        if spread_ok and leverage is not None:
            spread_bps = spread_fact.value * 100
            if spread_bps >= _TYPE_C_SPREAD_THRESHOLD_BPS and leverage >= _TYPE_C_LEVERAGE_THRESHOLD:
                type_c = "FLAGGED"
                notes.append(
                    f"High-yield credit spread at {spread_bps:.0f}bps (elevated) and net debt/revenue "
                    f"at {leverage:.2f}x — debt-funded capex is exposed to rising financing costs."
                )
            else:
                type_c = "NOT_FLAGGED"
                notes.append(
                    f"High-yield credit spread {spread_bps:.0f}bps and leverage {leverage:.2f}x — below flag thresholds."
                )
        else:
            type_c = "DATA_NOT_AVAILABLE"
            notes.append(
                "Type C assessment requires FRED_API_KEY (credit spread) and net-debt/revenue data; one or both missing."
            )

        type_a = "DATA_NOT_AVAILABLE"
        notes.append(
            "Type A (aggregate hyperscaler capex direction) has no free structured data source in this build — "
            "the Research Agent should look for capex guidance in recent SEC 8-K/10-Q filings instead of this "
            "agent asserting a verdict."
        )
        type_b = "DATA_NOT_AVAILABLE"
        notes.append(
            "Type B (yield-parity / in-house chip substitution) is a qualitative industry judgment with no free "
            "structured data source — left to the Research/Critic agents to address from filings/news, not inferred here."
        )

        return MacroResult(
            facts={k: v for k, v in macro_facts.items()},
            risk_flags=MacroRiskFlags(type_a=type_a, type_b=type_b, type_c=type_c, notes=notes),
        )
