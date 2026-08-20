"""Joey Park U.S. Equity Investment Agent — Streamlit dashboard.

Run with: streamlit run ui/app.py

Design intent (master-spec section 32): a prioritized, decision-focused
interface, not a data-maximalist "Bloomberg clone" — each view answers one
question a portfolio manager actually asks, and no view aggregates raw feeds
without a point of view.

UI copy (labels/titles/messages/table headers) is in Korean for readability.
Internal sentinel values (e.g. "DATA_NOT_AVAILABLE", "Bullish"/"Neutral"/
"Bearish" from the Decision Agent) are NOT changed at the data layer — they
are only translated for display here, via the *_KR mapping dicts below —
so nothing in joey_park/ (scoring, thesis tracking, tests) is affected.
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
from pathlib import Path

# Some cloud hosts (e.g. Streamlit Community Cloud's minimal container) run
# Python with a non-UTF-8 default stream encoding (bare/POSIX locale), which
# raises UnicodeEncodeError the moment anything — our own logging, or a
# dependency's internal debug logging — tries to write the Korean text this
# app generates to stdout/stderr. Force UTF-8 before anything else runs, the
# same fix already applied to joey_park/cli.py.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from joey_park.agents.portfolio_agent import PortfolioAgent  # noqa: E402
from joey_park.agents.risk_agent import RiskAgent  # noqa: E402
from joey_park.analytics.investor_archetype import classify_portfolio  # noqa: E402
from joey_park.analytics.temperature import compute_temperature  # noqa: E402
from joey_park.bootstrap import build_orchestrator  # noqa: E402
from joey_park.report import render_markdown  # noqa: E402

# Dark + mint theme, echoing the visual reference the user pointed to
# (yp-radar.vercel.app) — not a literal clone of any third party's brand
# assets, just the same dark-background / mint-accent / red-down convention
# common to Korean fintech dashboards.
_BG = "#0B0F14"
_PANEL = "#141A21"
_MINT = "#2DD4BF"
_RED = "#F87171"
_GRAY = "#8B98A5"


def _dark_plotly(fig: go.Figure, height: int = 520) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=_BG,
        plot_bgcolor=_PANEL,
        font_color="#E6EDF3",
        height=height,
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor="#22303C", zerolinecolor="#3A4A58")
    fig.update_yaxes(gridcolor="#22303C", zerolinecolor="#3A4A58")
    return fig

st.set_page_config(page_title="Joey Park U.S. Equity Investment Agent", layout="wide")

# ---- display-only Korean mappings (data layer stays in English) ----------
VIEW_KR = {"Bullish": "긍정적 (Bullish)", "Neutral": "중립 (Neutral)", "Bearish": "부정적 (Bearish)"}
CONF_KR = {"High": "높음", "Medium": "보통", "Low": "낮음"}
HORIZON_KR = {"Short": "단기", "Medium": "중기", "Long": "장기"}
SECTOR_LABELS_KR = {
    # our own sector_universe.yaml keys (used in Compare's sector picker)
    "semiconductor": "반도체",
    "ai_software_cloud": "AI 소프트웨어 & 클라우드",
    "power_infrastructure": "전력 인프라",
    "crypto_fintech": "가상자산 & 핀테크",
    "biotech_applied_ai": "바이오텍 & Applied AI",
    "value_anchors": "가치주 (전통 우량주)",
    # yfinance's own sector taxonomy (report.sector / position sector come from here)
    "Technology": "기술",
    "Healthcare": "헬스케어",
    "Financial Services": "금융",
    "Consumer Cyclical": "경기소비재",
    "Consumer Defensive": "필수소비재",
    "Industrials": "산업재",
    "Energy": "에너지",
    "Utilities": "유틸리티",
    "Real Estate": "부동산",
    "Basic Materials": "소재",
    "Communication Services": "통신서비스",
}
THESIS_CHANGE_KR = {
    "NEW": "신규 분석",
    "STRENGTHENED": "논지 강화",
    "UNCHANGED": "변화 없음",
    "WEAKENED": "논지 약화",
    "BROKEN": "논지 붕괴",
}
COLUMN_KR = {
    "ticker": "티커",
    "company_name": "회사명",
    "sector": "섹터",
    "industry": "산업",
    "overall_score": "종합점수",
    "investment_view": "투자의견",
    "confidence": "신뢰도",
    "analysis_date": "분석일시",
    "shares": "보유수량",
    "cost_basis": "매입단가",
    "last_price": "현재가",
    "market_value": "평가금액",
    "unrealized_p&l": "평가손익",
    "method": "밸류에이션 방법",
    "value": "값",
    "verdict": "판정",
    "note": "설명",
    "dimension": "평가항목",
    "score": "점수",
    "pct": "비중",
}


def _view_kr(v: str | None) -> str:
    return VIEW_KR.get(v, v or "N/A")


def _conf_kr(v: str | None) -> str:
    return CONF_KR.get(v, v or "N/A")


def _kr_cols(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=COLUMN_KR)


def _not_available_kr(text: str | None) -> str:
    if text and text.startswith("DATA_NOT_AVAILABLE"):
        return "데이터 없음 — " + text
    return text or "데이터 없음"


@st.cache_resource
def _app():
    orchestrator, db, settings = build_orchestrator()
    limits = settings.config["risk"]["position_limits"]
    portfolio_agent = PortfolioAgent(
        RiskAgent(), limits["max_single_position_pct"], limits["max_sector_pct"]
    )
    return orchestrator, db, settings, portfolio_agent


orchestrator, db, settings, portfolio_agent = _app()

if not settings.is_llm_configured():
    st.warning(
        "ANTHROPIC_API_KEY가 .env에 설정되어 있지 않습니다 — Research/Critic/Decision 에이전트는 "
        "실제 투자의견 대신 '데이터 없음(DATA_NOT_AVAILABLE)'을 반환합니다. 정량 점수(재무/밸류에이션/"
        "모멘텀 등)는 API 키 없이도 정상적으로 계산됩니다."
    )

PAGE_LABELS = {
    "Watchlist": "관심종목",
    "Stock Research": "종목 분석",
    "Compare": "종목 비교",
    "Stock Map": "종목 지도",
    "Portfolio": "포트폴리오",
    "Thesis": "투자논지 추적",
    "Alerts": "알림",
    "Reports": "리포트",
}
PAGES = list(PAGE_LABELS.keys())
page = st.sidebar.radio("메뉴", PAGES, format_func=lambda p: PAGE_LABELS[p])
st.sidebar.markdown("---")
st.sidebar.caption("Joey Park U.S. Equity Investment Agent — 미국주식 투자 리서치 에이전트")

if "reports" not in st.session_state:
    st.session_state.reports = {}  # ticker -> AnalysisReport


def run_analysis(ticker: str, add_to_watchlist: bool = False):
    with st.spinner(f"{ticker} 전체 파이프라인 실행 중..."):
        report = orchestrator.analyze(ticker)
        if add_to_watchlist:
            db.set_watchlist(report.ticker, True)
        st.session_state.reports[report.ticker] = report
    return report


def run_analyses_parallel(tickers: list[str], max_workers: int = 3) -> dict[str, str]:
    """Runs orchestrator.analyze for each ticker concurrently (I/O-bound: data
    fetch + LLM calls), instead of one-at-a-time. Each ticker still takes its
    own ~30-90s (data + 3 sequential LLM calls can't be shortened per-ticker),
    but N tickers no longer multiply that wall-clock time by N.
    max_workers is capped at 3 by default to stay under typical Anthropic
    per-minute rate limits (each ticker makes 3 LLM calls).
    Returns {ticker: error_message} for any that failed.
    """
    errors: dict[str, str] = {}
    if not tickers:
        return errors
    progress = st.progress(0.0, text=f"0/{len(tickers)} 완료")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {executor.submit(orchestrator.analyze, t): t for t in tickers}
        done = 0
        for future in concurrent.futures.as_completed(future_to_ticker):
            t = future_to_ticker[future]
            done += 1
            try:
                report = future.result()
                st.session_state.reports[report.ticker] = report
            except Exception as exc:
                errors[t] = str(exc)
            progress.progress(done / len(tickers), text=f"{done}/{len(tickers)} 완료 ({t})")
    progress.empty()
    return errors


# ---------------------------------------------------------------- 관심종목
if page == "Watchlist":
    st.title("관심종목")
    rows = db.get_watchlist()
    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        st.dataframe(_kr_cols(df[["ticker", "company_name", "sector", "industry"]]), use_container_width=True)
    else:
        st.info("관심종목이 비어 있습니다. '종목 분석' 메뉴에서 티커를 추가하세요.")

    st.subheader("관심종목 최신 점수")
    score_rows = []
    for r in rows:
        latest = db.get_latest_result(r["ticker"])
        if latest:
            score_rows.append(
                {
                    "ticker": r["ticker"],
                    "overall_score": latest["overall_score"],
                    "investment_view": _view_kr(latest["investment_view"]),
                    "confidence": _conf_kr(latest["confidence"]),
                    "analysis_date": latest["analysis_date"],
                }
            )
    if score_rows:
        st.dataframe(_kr_cols(pd.DataFrame(score_rows)), use_container_width=True)
    else:
        st.caption("아직 분석을 실행한 관심종목이 없습니다.")

# ------------------------------------------------------------ 종목 분석
elif page == "Stock Research":
    st.title("종목 분석")
    col1, col2 = st.columns([3, 1])
    ticker = col1.text_input("티커", value="MSFT").upper().strip()
    add_watch = col2.checkbox("관심종목에 추가", value=False)

    if st.button("분석 실행", type="primary"):
        run_analysis(ticker, add_watch)

    report = st.session_state.reports.get(ticker)
    if report is None:
        latest = db.get_latest_result(ticker)
        if latest:
            st.info(f"{latest['analysis_date']}에 저장된 마지막 분석을 표시합니다. 갱신하려면 '분석 실행'을 누르세요.")
            st.json(
                {
                    "investment_view": latest["investment_view"],
                    "confidence": latest["confidence"],
                    "overall_score": latest["overall_score"],
                    "thesis": latest["thesis"],
                }
            )
        else:
            st.info("이 티커에 대한 분석이 아직 없습니다. '분석 실행'을 눌러주세요.")
    else:
        d = report.decision
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("투자의견", _view_kr(d.investment_view))
        c2.metric("신뢰도", _conf_kr(d.confidence))
        c3.metric("종합점수", f"{report.overall_score:.2f}" if report.overall_score is not None else "N/A")
        c4.metric("데이터 완전성", f"{report.completeness_pct:.0%}")

        if report.data_quality_warnings:
            st.warning(" · ".join(report.data_quality_warnings))
        if report.thesis_change.classification != "NEW":
            st.info(
                f"투자논지 변화: {THESIS_CHANGE_KR.get(report.thesis_change.classification, report.thesis_change.classification)} "
                f"— {report.thesis_change.reason}"
            )

        st.subheader("핵심 투자논지 (Thesis)")
        st.write(_not_available_kr(d.thesis))

        bull_tab, base_tab, bear_tab = st.tabs(["낙관 시나리오 (Bull)", "기본 시나리오 (Base)", "비관 시나리오 (Bear)"])
        for tab, case in zip((bull_tab, base_tab, bear_tab), (d.bull_case, d.base_case, d.bear_case)):
            with tab:
                st.write(_not_available_kr(case.get("narrative")))
                if isinstance(case.get("probability"), (int, float)):
                    st.caption(f"발생 확률: {case['probability']:.0%}")

        st.subheader("평가 항목별 점수")
        scores_df = pd.DataFrame(
            [{"dimension": k, "score": v} for k, v in report.dimension_scores.items()]
        )
        st.bar_chart(_kr_cols(scores_df).set_index("평가항목"))

        st.subheader("밸류에이션")
        st.write(_not_available_kr(d.valuation_summary))
        st.dataframe(_kr_cols(pd.DataFrame([v.__dict__ for v in report.valuation.verdicts])), use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("주요 촉매(Catalysts)")
            for c in d.catalysts or ["DATA_NOT_AVAILABLE"]:
                st.write(f"- {_not_available_kr(c)}")
        with col_b:
            st.subheader("주요 리스크")
            for rk in d.risks or ["DATA_NOT_AVAILABLE"]:
                st.write(f"- {_not_available_kr(rk)}")

        st.subheader("판단을 바꿀 조건 (What Would Change My Mind)")
        st.write(_not_available_kr(d.what_would_change_my_mind))

        st.caption("아래 상세 패널은 원본 데이터 검증용으로 필드명이 영문(원본 그대로)입니다.")
        with st.expander("Critic(검증) 에이전트 결과"):
            st.json(report.critic.__dict__)
        with st.expander("Research(리서치) 에이전트 전체 결과"):
            st.json(report.research.__dict__)
        with st.expander("매크로 리스크 플래그"):
            st.json(report.macro.risk_flags.__dict__)
        with st.expander("전체 리포트 다운로드 (Markdown)"):
            st.code(render_markdown(report), language="markdown")

# ------------------------------------------------------------------- 종목 비교
elif page == "Compare":
    st.title("종목 비교")
    tickers_input = st.text_input("티커 (쉼표로 구분)", value="MSFT, GOOGL, ORCL")
    typed_tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    sector_picks: list[str] = []
    with st.expander(f"섹터별 종목에서 선택 (총 {sum(len(v['tickers']) for v in settings.sector_universe.values())}개)"):
        for sector_key, sector in settings.sector_universe.items():
            sector_label = SECTOR_LABELS_KR.get(sector_key, sector_key)
            picked = st.multiselect(
                f"{sector_label} — {sector['description'].strip()}",
                options=sector["tickers"],
                key=f"sector_pick_{sector_key}",
            )
            sector_picks.extend(picked)

    tickers = list(dict.fromkeys(typed_tickers + sector_picks))  # union, de-duplicated, order-preserving
    if sector_picks:
        st.caption(f"직접 입력 {len(typed_tickers)}개 + 섹터 선택 {len(sector_picks)}개 = 총 {len(tickers)}개 비교")

    if st.button("전체 실행 / 갱신 (병렬)"):
        errors = run_analyses_parallel(tickers)
        if errors:
            st.warning("일부 티커 분석 실패: " + ", ".join(f"{t} ({e})" for t, e in errors.items()))

    rows = []
    for t in tickers:
        report = st.session_state.reports.get(t)
        latest = db.get_latest_result(t)
        if report:
            rows.append(
                {
                    "ticker": t,
                    "overall_score": report.overall_score,
                    "investment_view": _view_kr(report.decision.investment_view),
                    "confidence": _conf_kr(report.decision.confidence),
                    **{f"score_{k}": v for k, v in report.dimension_scores.items()},
                }
            )
        elif latest:
            rows.append(
                {
                    "ticker": t,
                    "overall_score": latest["overall_score"],
                    "investment_view": _view_kr(latest["investment_view"]),
                    "confidence": _conf_kr(latest["confidence"]),
                }
            )
    if rows:
        st.dataframe(_kr_cols(pd.DataFrame(rows).sort_values("overall_score", ascending=False)), use_container_width=True)
    else:
        st.info("'전체 실행 / 갱신' 버튼을 눌러 위 티커들을 비교하세요.")

# ------------------------------------------------------------------- 종목 지도
elif page == "Stock Map":
    st.title("종목 지도")
    st.caption(
        "이 세션에서 분석한 종목들을 밸류에이션 점수(X) × 이상신호 온도(Y)로 배치합니다. "
        "온도는 최근 10일 수익률·거래량·변동성이 자기 자신의 과거 분포에서 얼마나 벗어났는지를 "
        "합성한 지표입니다 (config 없이 항상 계산되는 결정론적 값, LLM 미사용)."
    )

    map_rows = []
    for t, report in st.session_state.reports.items():
        temp = compute_temperature(report.market) if report.market else None
        map_rows.append(
            {
                "ticker": t,
                "sector": SECTOR_LABELS_KR.get(report.sector, report.sector or "미분류"),
                "valuation_score": report.dimension_scores.get("valuation"),
                "temperature": temp.temperature if temp else None,
                "temperature_label": temp.label if temp else "DATA_NOT_AVAILABLE",
                "overall_score": report.overall_score,
                "investment_view": _view_kr(report.decision.investment_view),
            }
        )
    map_df = pd.DataFrame(map_rows).dropna(subset=["valuation_score", "temperature"])

    if map_df.empty:
        st.info(
            "표시할 데이터가 없습니다. '종목 분석' 또는 '종목 비교'에서 먼저 몇 개 종목을 분석해 주세요 "
            "(이 페이지는 이번 세션에서 분석된 종목만 표시합니다 — 가격 이력이 DB에 저장되지 않기 때문입니다)."
        )
    else:
        fig = px.scatter(
            map_df,
            x="valuation_score",
            y="temperature",
            color="sector",
            size="overall_score",
            size_max=32,
            hover_name="ticker",
            hover_data={"investment_view": True, "temperature_label": True, "valuation_score": ":.2f", "temperature": ":.2f"},
            color_discrete_sequence=[_MINT, "#60A5FA", "#FBBF24", "#F472B6", "#A78BFA", _RED, _GRAY],
        )
        fig.add_vline(x=0.5, line_dash="dot", line_color="#3A4A58")
        fig.add_hline(y=1.5, line_dash="dot", line_color="#3A4A58")
        fig.update_traces(marker=dict(line=dict(width=1, color=_BG)))
        fig.update_layout(xaxis_title="밸류에이션 점수 (높을수록 저평가)", yaxis_title="이상신호 온도")
        st.plotly_chart(_dark_plotly(fig), use_container_width=True)

        st.subheader("섹터별 종목 트리맵")
        treemap_df = map_df.copy()
        treemap_df["size"] = 1
        tfig = px.treemap(
            treemap_df,
            path=["sector", "ticker"],
            values="size",
            color="overall_score",
            color_continuous_scale=[_RED, _GRAY, _MINT],
            range_color=[0, 1],
            hover_data={"investment_view": True},
        )
        st.plotly_chart(_dark_plotly(tfig, height=420), use_container_width=True)

# ----------------------------------------------------------------- 포트폴리오
elif page == "Portfolio":
    st.title("포트폴리오")

    with st.expander("포지션 추가", expanded=(len(db.get_open_positions()) == 0)):
        with st.form("add_position_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            new_ticker = c1.text_input("티커").upper().strip()
            new_shares = c2.number_input("보유수량", min_value=0.0, step=1.0)
            new_cost_basis = c3.number_input("매입단가 (주당)", min_value=0.0, step=0.01)
            new_notes = st.text_input("메모 (선택)")
            submitted = st.form_submit_button("포지션 추가")
            if submitted:
                if not new_ticker or new_shares <= 0:
                    st.error("티커와 0보다 큰 보유수량은 필수입니다.")
                else:
                    db.add_position(new_ticker, new_shares, new_cost_basis or None, new_notes or None)
                    st.success(f"{new_ticker} {new_shares:g}주를 추가했습니다.")
                    st.rerun()

    positions = db.get_open_positions()
    if not positions:
        st.info("아직 보유 포지션이 없습니다. 위에서 추가해 주세요.")
    else:
        rows = []
        portfolio_agent_rows = []
        for p in positions:
            latest = db.get_latest_result(p["ticker"])
            stock = db.get_stock(p["ticker"])
            price = latest["price_at_analysis"] if latest else None
            sector = stock["sector"] if stock else None
            market_value = (price or 0) * p["shares"]
            unrealized_pl = (
                (price - p["cost_basis"]) * p["shares"] if price is not None and p["cost_basis"] else None
            )
            rows.append(
                {
                    "position_id": p["position_id"],
                    "ticker": p["ticker"],
                    "shares": p["shares"],
                    "cost_basis": p["cost_basis"],
                    "last_price": price,
                    "market_value": market_value,
                    "unrealized_p&l": unrealized_pl,
                    "sector": sector or "알 수 없음 (해당 티커 분석 실행 시 자동 채워짐)",
                }
            )
            portfolio_agent_rows.append(
                {
                    "ticker": p["ticker"],
                    "market_value": market_value,
                    "sector": sector,
                    "overall_score": latest["overall_score"] if latest else None,
                    "growth_score": latest["growth_score"] if latest else None,
                    "valuation_score": latest["valuation_score"] if latest else None,
                    "momentum_score": latest["momentum_score"] if latest else None,
                    "quality_score": latest["quality_score"] if latest else None,
                }
            )

        df = pd.DataFrame(rows)
        st.dataframe(_kr_cols(df.drop(columns=["position_id"])), use_container_width=True)
        st.metric("총 평가금액", f"${df['market_value'].sum():,.0f}")

        st.subheader("포지션 종료")
        close_col1, close_col2 = st.columns([3, 1])
        to_close = close_col1.selectbox(
            "포지션 선택", options=[f"{r['ticker']} ({r['shares']:g}주)" for r in rows], key="close_select"
        )
        if close_col2.button("종료", type="secondary"):
            idx = [f"{r['ticker']} ({r['shares']:g}주)" for r in rows].index(to_close)
            db.close_position(rows[idx]["position_id"])
            st.success(f"{to_close} 포지션을 종료했습니다.")
            st.rerun()

        st.subheader("섹터 노출도 & 집중도 (마스터 스펙 16번 항목)")
        summary = portfolio_agent.summarize(portfolio_agent_rows)
        if summary.total_market_value > 0:
            exposure_df = pd.DataFrame(
                [{"섹터": SECTOR_LABELS_KR.get(e.sector, e.sector), "비중": e.pct_of_portfolio} for e in summary.sector_exposures]
            )
            st.bar_chart(exposure_df.set_index("섹터"))
            for cw in summary.concentration_warnings:
                if cw.kind == "sector":
                    st.warning(f"섹터 '{SECTOR_LABELS_KR.get(cw.label, cw.label)}'가 포트폴리오의 {cw.pct:.1%}를 차지 — 한도 {cw.limit:.0%} 초과")
                else:
                    st.warning(f"{cw.label}이(가) 포트폴리오의 {cw.pct:.1%}를 차지 — 한도 {cw.limit:.0%} 초과")
            if not summary.concentration_warnings:
                st.caption("설정된 집중도 한도(config.yaml risk.position_limits)를 초과한 종목/섹터가 없습니다.")

        st.subheader("종목 트리맵")
        tm_df = pd.DataFrame(
            [
                {
                    "sector": SECTOR_LABELS_KR.get(r["sector"], r["sector"] or "미분류"),
                    "ticker": r["ticker"],
                    "market_value": max(r["market_value"], 0.01),
                    "overall_score": r["overall_score"] if r["overall_score"] is not None else 0.5,
                }
                for r in portfolio_agent_rows
            ]
        )
        pfig = px.treemap(
            tm_df, path=["sector", "ticker"], values="market_value", color="overall_score",
            color_continuous_scale=[_RED, _GRAY, _MINT], range_color=[0, 1],
        )
        st.plotly_chart(_dark_plotly(pfig, height=420), use_container_width=True)

        st.subheader("투자자 유형 (포트폴리오 구성 기반, Recommended Enhancement)")
        archetype = classify_portfolio(portfolio_agent_rows)
        if archetype is None:
            st.caption(
                "종목별 평가 점수가 아직 부족해 유형을 판정할 수 없습니다 "
                "('종목 분석'에서 보유 종목을 한 번씩 분석해 주세요)."
            )
        else:
            st.markdown(f"## {archetype.icon} {archetype.name}")
            st.write(archetype.description)
            st.caption(archetype.concentration_note)
            ac1, ac2 = st.columns(2)
            ac1.metric("성장 vs 가치 축", f"{archetype.growth_axis:+.2f}", help="양수=성장 편향, 음수=가치 편향")
            ac2.metric("공격 vs 안정 축", f"{archetype.aggression_axis:+.2f}", help="양수=모멘텀 추격, 음수=퀄리티/안정 추구")
            st.caption("현재 보유 종목의 평가 점수를 규칙 기반으로 조합한 결과이며, 투자 성향 진단이 아니라 현재 포트폴리오 구성의 스냅샷입니다.")

# --------------------------------------------------------------------- 투자논지 추적
elif page == "Thesis":
    st.title("투자논지 추적 (Thesis Tracking)")
    ticker = st.text_input("티커", value="MSFT").upper().strip()
    history = db.get_thesis_history(ticker, limit=20)
    if not history:
        st.info("이 티커의 투자논지 이력이 아직 없습니다.")
    else:
        for row in history:
            change_label = THESIS_CHANGE_KR.get(row["change_vs_prior"], row["change_vs_prior"])
            with st.expander(f"{row['recorded_at']} — {change_label}"):
                st.write(_not_available_kr(row["thesis_summary"]))
                st.caption(row["change_reason"])
                if row["key_risks"]:
                    st.write("**주요 리스크:**")
                    for rk in json.loads(row["key_risks"]):
                        st.write(f"- {rk}")

# --------------------------------------------------------------------- 알림
elif page == "Alerts":
    st.title("알림")
    alerts = db.get_unacknowledged_alerts()
    if not alerts:
        st.info("확인하지 않은 알림이 없습니다.")
    for a in alerts:
        severity_icon = {"CRITICAL": "🔴", "WARNING": "🟠", "INFO": "🔵"}.get(a["severity"], "⚪")
        st.write(f"{severity_icon} **{a['ticker']}** — {a['alert_type']} ({a['created_at']})")
        st.caption(a["message"])

# -------------------------------------------------------------------- 리포트
elif page == "Reports":
    st.title("리포트")
    ticker = st.text_input("티커", value="MSFT").upper().strip()
    history = db.get_result_history(ticker, limit=10)
    if not history:
        st.info("이 티커에 저장된 분석이 아직 없습니다.")
    else:
        options = [row["analysis_date"] for row in history]
        selected = st.selectbox("분석 일시", options)
        row = next(r for r in history if r["analysis_date"] == selected)
        st.caption("아래는 DB에 저장된 원본 레코드입니다 (필드명은 영문 그대로).")
        st.json(dict(row))
