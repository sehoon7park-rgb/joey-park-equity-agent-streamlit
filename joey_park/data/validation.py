"""Data Quality Gate — runs before any analysis, per master-spec section 15.

Checks are deterministic and cheap; failures produce warnings attached to
the report rather than blocking the pipeline outright (a stale price is a
reason to lower confidence, not a reason to refuse to analyze a stock).
"""
from __future__ import annotations

from datetime import date, timedelta

from joey_park.data.models import (
    DataQualityReport,
    DataStatus,
    Fact,
    FinancialSnapshot,
    MarketSnapshot,
)


def _is_missing(fact: Fact | None) -> bool:
    return fact is None or fact.status != DataStatus.OK or fact.value is None


def run_data_quality_gate(
    ticker: str,
    market: MarketSnapshot,
    financials: FinancialSnapshot,
    price_staleness_days: int,
    fundamentals_staleness_days: int,
    min_completeness_pct: float,
) -> DataQualityReport:
    checks_run: list[str] = []
    warnings: list[str] = []
    has_critical_error = False  # tracked as a flag, not by matching warning text (which is now Korean)

    # 1. Price staleness
    checks_run.append("price_staleness")
    if market.last_price.status == DataStatus.OK and market.last_price.period_date:
        age_days = (date.today() - market.last_price.period_date).days
        if age_days > price_staleness_days:
            warnings.append(
                f"최근 가격이 {age_days}일 전 데이터입니다 (기준 {price_staleness_days}일) — 시장이 정지/휴장 상태일 수 있습니다."
            )
    else:
        warnings.append("최근 가격 데이터를 가져오지 못했습니다.")

    # 2. Fundamentals staleness
    checks_run.append("fundamentals_staleness")
    if financials.fiscal_period_end:
        age_days = (date.today() - financials.fiscal_period_end).days
        if age_days > fundamentals_staleness_days:
            warnings.append(
                f"최근 회계기간이 {age_days}일 전 자료입니다 (기준 {fundamentals_staleness_days}일) — "
                "다음 실적 발표 시 크게 바뀔 수 있습니다."
            )
    else:
        warnings.append("회계기간 종료일 정보를 가져오지 못했습니다.")

    # 3. Abnormal values (sanity bounds — not a model, just guardrails)
    checks_run.append("abnormal_values")
    if market.last_price.status == DataStatus.OK and market.last_price.value is not None:
        if market.last_price.value <= 0:
            warnings.append("최근 가격이 0 이하입니다 — 데이터 오류로 보입니다.")
            has_critical_error = True
    if financials.gross_margin.status == DataStatus.OK and financials.gross_margin.value is not None:
        if not (-1.0 <= financials.gross_margin.value <= 1.0):
            warnings.append(f"매출총이익률 {financials.gross_margin.value}이(가) 타당한 범위(-100%~100%)를 벗어났습니다.")

    # 4. Duplicated/degenerate price history
    checks_run.append("price_history_variance")
    if market.price_history and len(market.price_history) > 5:
        closes = {bar.close for bar in market.price_history[-20:]}
        if len(closes) == 1:
            warnings.append("최근 20개 가격 데이터가 전부 동일합니다 — 데이터 피드가 멈춰있을 가능성이 있습니다.")

    # 5. Completeness score across the fields analysis actually depends on
    checks_run.append("completeness")
    tracked_facts = [
        market.last_price,
        financials.revenue,
        financials.revenue_yoy_growth,
        financials.gross_margin,
        financials.operating_margin,
        financials.fcf,
        financials.forward_pe,
        financials.trailing_pe,
        financials.ev_to_ebitda,
    ]
    available = sum(0 if _is_missing(f) else 1 for f in tracked_facts)
    completeness_pct = available / len(tracked_facts)
    if completeness_pct < min_completeness_pct:
        warnings.append(
            f"데이터 완전성 {completeness_pct:.0%}이(가) 기준({min_completeness_pct:.0%})보다 낮습니다 "
            "— 신뢰도를 '낮음'으로 제한해야 합니다."
        )

    passed = completeness_pct >= min_completeness_pct and not has_critical_error

    return DataQualityReport(
        ticker=ticker,
        checks_run=checks_run,
        warnings=warnings,
        completeness_pct=completeness_pct,
        passed=passed,
    )
