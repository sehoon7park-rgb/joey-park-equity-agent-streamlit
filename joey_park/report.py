"""Renders an AnalysisReport into a Markdown investment report, following
the structure fixed by master-spec sections 12-13: numbers, narrative, and
decision are visually separated, not blended.

Display copy (headers/labels) is Korean, matching ui/app.py. Internal data
values (report.decision.investment_view etc.) stay in English at the data
layer — this module only translates them for display, via the small *_KR
maps below, mirroring the same pattern used in ui/app.py.
"""
from __future__ import annotations

from joey_park.agents.orchestrator import AnalysisReport

_VIEW_KR = {"Bullish": "긍정적 (Bullish)", "Neutral": "중립 (Neutral)", "Bearish": "부정적 (Bearish)"}
_CONF_KR = {"High": "높음", "Medium": "보통", "Low": "낮음"}
_HORIZON_KR = {"Short": "단기", "Medium": "중기", "Long": "장기"}
_THESIS_CHANGE_KR = {
    "NEW": "신규 분석",
    "STRENGTHENED": "논지 강화",
    "UNCHANGED": "변화 없음",
    "WEAKENED": "논지 약화",
    "BROKEN": "논지 붕괴",
}
_NA = "데이터 없음"


def _kr(mapping: dict[str, str], v: str | None) -> str:
    return mapping.get(v, v or _NA)


def _text(v: str | None) -> str:
    if not v:
        return _NA
    if v.startswith("DATA_NOT_AVAILABLE"):
        return f"{_NA} — {v}"
    return v


def _fmt_pct(x: float | None) -> str:
    return f"{x:.1%}" if x is not None else _NA


def _fmt_score(x: float | None) -> str:
    return f"{x:.2f}" if x is not None else "N/A"


def render_markdown(report: AnalysisReport) -> str:
    d = report.decision
    lines: list[str] = []
    lines.append(f"# Joey Park U.S. Equity Investment Agent — {report.ticker}")
    lines.append(f"_분석일시: {report.analysis_date} · Run ID: {report.run_id}_")
    lines.append("")
    if report.errors:
        lines.append("> **경고:** " + "; ".join(report.errors))
    if report.data_quality_warnings:
        lines.append("> **데이터 품질:** " + "; ".join(report.data_quality_warnings))
    lines.append("")

    lines.append("## 투자의견")
    lines.append(f"- **의견:** {_kr(_VIEW_KR, d.investment_view)}")
    lines.append(f"- **신뢰도:** {_kr(_CONF_KR, d.confidence)} (근거의 질 — 아래 데이터 레이어 참고, 점수와는 별개)")
    lines.append(f"- **투자 기간:** {_kr(_HORIZON_KR, d.time_horizon)}")
    lines.append(f"- **분석 시점 가격:** {report.price_at_analysis}")
    lines.append(
        f"- **직전 분석 대비 논지 변화:** {_kr(_THESIS_CHANGE_KR, report.thesis_change.classification)} — {report.thesis_change.reason}"
    )
    lines.append("")
    lines.append(f"**핵심 투자논지:** {_text(d.thesis)}")
    lines.append("")

    lines.append("## 시나리오")
    for label, case in (("낙관 시나리오 (Bull)", d.bull_case), ("기본 시나리오 (Base)", d.base_case), ("비관 시나리오 (Bear)", d.bear_case)):
        prob = case.get("probability") if case else None
        narrative = case.get("narrative") if case else None
        lines.append(f"### {label}" + (f" ({prob:.0%})" if isinstance(prob, (int, float)) else ""))
        lines.append(_text(narrative))
        lines.append("")

    lines.append("## 밸류에이션")
    lines.append(_text(d.valuation_summary))
    lines.append("")
    lines.append("| 방법 | 값 | 판정 | 설명 |")
    lines.append("|---|---|---|---|")
    for v in report.valuation.verdicts:
        val_str = f"{v.value:.2f}" if isinstance(v.value, (int, float)) else "N/A"
        lines.append(f"| {v.method} | {val_str} | {v.verdict} | {v.note} |")
    lines.append("")

    lines.append("## 주요 촉매 (Catalysts)")
    for c in d.catalysts or [_NA]:
        lines.append(f"- {_text(c)}")
    lines.append("")

    lines.append("## 주요 리스크")
    for r in d.risks or [_NA]:
        lines.append(f"- {_text(r)}")
    lines.append("")

    lines.append("## 판단을 바꿀 조건 (What Would Change My Mind)")
    lines.append(_text(d.what_would_change_my_mind))
    lines.append("")

    lines.append("## 평가 항목별 점수 (데이터 레이어 — LLM 추정이 아닌 실계산값)")
    lines.append("| 평가항목 | 점수 |")
    lines.append("|---|---|")
    for k, v in report.dimension_scores.items():
        lines.append(f"| {k} | {_fmt_score(v)} |")
    lines.append(f"| **종합점수** | **{_fmt_score(report.overall_score)}** |")
    lines.append(f"\n데이터 완전성: {_fmt_pct(report.completeness_pct)}")
    lines.append("")

    lines.append("## 매크로 리스크 플래그")
    flags = report.macro.risk_flags
    lines.append(f"- Type A (전제붕괴): {flags.type_a}")
    lines.append(f"- Type B (내부재편): {flags.type_b}")
    lines.append(f"- Type C (자기잠식): {flags.type_c}")
    for note in flags.notes:
        lines.append(f"  - {note}")
    lines.append("")

    lines.append("## 포지션 리스크")
    pr = report.position_risk
    lines.append(f"- 연환산 변동성: {_fmt_pct(pr.annualized_volatility)}")
    lines.append(f"- 베타: {pr.beta if pr.beta is not None else _NA}")
    lines.append(f"- 최근 1년 최대낙폭: {_fmt_pct(pr.max_drawdown_1y)}")
    for note in pr.notes:
        lines.append(f"  - {note}")
    lines.append("")

    lines.append("## 리서치 내러티브 (레이어 2 — 위 숫자 레이어와 분리된 서술)")
    lines.append(f"**사업 개요:** {_text(report.research.business_summary)}")
    lines.append(f"\n**퀄리티 노트:** {_text(report.research.quality_notes)}")
    lines.append(f"\n**경쟁 위치:** {_text(report.research.competitive_position)}")
    if report.research.data_gaps:
        lines.append("\n**Research 에이전트가 표시한 데이터 공백:**")
        for gap in report.research.data_gaps:
            lines.append(f"- {gap}")
    lines.append("")

    lines.append("## Critic (검증) 에이전트 결과")
    c = report.critic
    lines.append(f"- 판정: {c.verdict}")
    lines.append(f"- 숫자-근거 일치 여부: {c.numbers_match_facts}")
    lines.append(f"- 낙관 편향 감지: {c.bull_only_bias_detected}")
    lines.append(f"- 비관 시나리오 누락: {c.missing_bear_case}")
    if c.issues:
        lines.append("- 지적 사항:")
        for issue in c.issues:
            lines.append(f"  - {issue}")
    lines.append("")

    lines.append("## 출처 (Provenance)")
    lines.append(f"- 사용된 데이터 소스: {', '.join(report.data_sources) or '없음'}")
    if report.errors:
        lines.append(f"- 실행 중 발생한 오류: {', '.join(report.errors)}")

    return "\n".join(lines)
