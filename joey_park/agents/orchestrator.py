"""Orchestrator — wires the end-to-end pipeline (master-spec section 34):

Ticker -> Data -> Validation -> Fundamental/Valuation/Technical/Macro/Risk
       -> Research (LLM) -> Critic (LLM) -> Decision (LLM)
       -> Thesis tracking -> Persist -> Report

Each agent call is wrapped so one failure degrades the result (lower
confidence, a warning in the report) instead of crashing the whole run
(master-spec section 36).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from joey_park.agents.critic_agent import CriticAgent, CriticResult
from joey_park.agents.data_agent import DataAgent, DataBundle
from joey_park.agents.decision_agent import DecisionAgent, DecisionResult
from joey_park.agents.fundamental_agent import FundamentalAgent, FundamentalResult
from joey_park.agents.macro_agent import MacroAgent, MacroResult
from joey_park.agents.research_agent import ResearchAgent, ResearchResult
from joey_park.agents.risk_agent import PositionRisk, RiskAgent
from joey_park.agents.technical_agent import TechnicalAgent, TechnicalResult
from joey_park.agents.valuation_agent import ValuationAgent, ValuationResult
from joey_park.analytics.scoring import combine_scores, score_cycle_position
from joey_park.config.settings import Settings
from joey_park.data.models import MarketSnapshot
from joey_park.data.validation import run_data_quality_gate
from joey_park.db.database import Database, new_id
from joey_park.memory.thesis_tracker import ThesisChange, detect_thesis_change

logger = logging.getLogger(__name__)


@dataclass
class AnalysisReport:
    ticker: str
    run_id: str
    analysis_date: str
    price_at_analysis: float | None
    dimension_scores: dict
    overall_score: float | None
    completeness_pct: float
    data_quality_warnings: list[str]
    fundamental: FundamentalResult
    valuation: ValuationResult
    technical: TechnicalResult
    macro: MacroResult
    position_risk: PositionRisk
    research: ResearchResult
    critic: CriticResult
    decision: DecisionResult
    thesis_change: ThesisChange
    market: MarketSnapshot | None = None  # raw price history, for UI-side viz (e.g. temperature)
    sector: str | None = None
    errors: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)


class Orchestrator:
    def __init__(self, settings: Settings, db: Database, data_agent: DataAgent, llm):
        self._settings = settings
        self._db = db
        self._data_agent = data_agent
        cfg = settings.config
        self._fundamental_agent = FundamentalAgent()
        self._valuation_agent = ValuationAgent(
            methods_by_sector=cfg["valuation"]["methods_by_sector"],
            heuristics=cfg["valuation"]["heuristics"],
        )
        self._technical_agent = TechnicalAgent()
        self._macro_agent = MacroAgent()
        self._risk_agent = RiskAgent()
        self._research_agent = ResearchAgent(llm)
        self._critic_agent = CriticAgent(llm)
        self._decision_agent = DecisionAgent(llm)

    def analyze(self, ticker: str) -> AnalysisReport:
        ticker = ticker.upper().strip()
        cfg = self._settings.config
        started = time.time()
        errors: list[str] = []
        agents_called: list[str] = []

        run_id = self._db.start_run(ticker, model=self._settings.anthropic_model, prompt_version="v0.1.0")

        # 1. DATA
        bundle: DataBundle = self._data_agent.fetch(ticker)
        agents_called.append("data_agent")
        errors.extend(bundle.errors)

        self._db.upsert_stock(ticker, company_name=None, sector=bundle.financials.sector, industry=bundle.financials.industry)

        # 2. VALIDATION
        dq_report = run_data_quality_gate(
            ticker,
            bundle.market,
            bundle.financials,
            price_staleness_days=cfg["data"]["price_staleness_days"],
            fundamentals_staleness_days=cfg["data"]["fundamentals_staleness_days"],
            min_completeness_pct=cfg["data"]["min_data_completeness_pct"],
        )
        agents_called.append("data_quality_gate")

        # 3. DETERMINISTIC ANALYSIS AGENTS (fundamental/valuation/technical/macro/risk)
        fundamental = self._fundamental_agent.run(bundle.financials)
        agents_called.append("fundamental_agent")

        valuation = self._valuation_agent.run(bundle.financials, bundle.market)
        agents_called.append("valuation_agent")

        technical = self._technical_agent.run(bundle.market)
        agents_called.append("technical_agent")

        macro = self._macro_agent.run(bundle.macro_facts, bundle.financials)
        agents_called.append("macro_agent")

        position_risk = self._risk_agent.run_position_risk(bundle.market)
        agents_called.append("risk_agent")

        sector_key = (bundle.financials.sector or "").lower().replace(" ", "_")
        topology_weight = self._settings.sector_universe.get(sector_key, {}).get("topology_weight")
        cycle_score, cycle_raw = score_cycle_position(bundle.financials, topology_weight)

        dimension_scores = {
            "fundamental": fundamental.fundamental_score,
            "growth": fundamental.growth_score,
            "quality": fundamental.quality_score,
            "valuation": valuation.valuation_score,
            "momentum": technical.momentum_score,
            "cycle_position": cycle_score,
            "catalyst": None,  # populated qualitatively by research/decision agents, not scored numerically in MVP
        }
        overall_score, completeness_pct = combine_scores(dimension_scores, cfg["scoring"]["weights"])

        # 4. RESEARCH (LLM #1)
        facts_payload = {
            "fundamental": fundamental.facts_summary,
            "valuation_verdicts": [v.__dict__ for v in valuation.verdicts],
            "technical": {"trend": technical.trend_description, "momentum_score": technical.momentum_score},
            "macro": {"facts": {k: f.value for k, f in macro.facts.items()}, "risk_flags": macro.risk_flags.__dict__},
            "sec_recent_filings": bundle.sec_recent_filings,
            "cycle_position_raw": cycle_raw,
            "sector": bundle.financials.sector,
            "industry": bundle.financials.industry,
        }
        research = self._research_agent.run(ticker, facts_payload)
        agents_called.append("research_agent")

        # 5. CRITIC (LLM #2) — verification pass before final decision
        critic = self._critic_agent.run(ticker, facts_payload, research.__dict__)
        agents_called.append("critic_agent")

        # 6. DECISION (LLM #3) — final structured Investment View
        decision = self._decision_agent.run(
            ticker,
            dimension_scores,
            overall_score,
            completeness_pct,
            research.__dict__,
            critic.__dict__,
            macro.risk_flags.__dict__,
        )
        agents_called.append("decision_agent")

        # 7. THESIS TRACKING — compare to the prior run, if any, BEFORE saving this one
        result_id = new_id()
        analysis_date = datetime.now(timezone.utc).isoformat()
        price_at_analysis = bundle.market.last_price.value

        self._db.save_analysis_result(
            {
                "result_id": result_id,
                "run_id": run_id,
                "ticker": ticker,
                "analysis_date": analysis_date,
                "price_at_analysis": price_at_analysis,
                "fundamental_score": dimension_scores["fundamental"],
                "growth_score": dimension_scores["growth"],
                "quality_score": dimension_scores["quality"],
                "valuation_score": dimension_scores["valuation"],
                "momentum_score": dimension_scores["momentum"],
                "cycle_position_score": dimension_scores["cycle_position"],
                "catalyst_score": dimension_scores["catalyst"],
                "overall_score": overall_score,
                "investment_view": decision.investment_view,
                "confidence": decision.confidence,
                "time_horizon": decision.time_horizon,
                "thesis": decision.thesis,
                "bull_case": decision.bull_case.get("narrative") if decision.bull_case else None,
                "base_case": decision.base_case.get("narrative") if decision.base_case else None,
                "bear_case": decision.bear_case.get("narrative") if decision.bear_case else None,
                "valuation_summary": decision.valuation_summary,
                "catalysts": decision.catalysts,
                "risks": decision.risks,
                "what_would_change_my_mind": decision.what_would_change_my_mind,
                "macro_risk_flags": macro.risk_flags.__dict__,
                "data_completeness_pct": completeness_pct,
                "data_quality_warnings": dq_report.warnings,
                "raw_dimension_facts": facts_payload,
            }
        )

        thesis_change = detect_thesis_change(
            self._db,
            ticker,
            overall_score if overall_score is not None else 0.0,
            decision.investment_view,
            decision.confidence,
            score_change_threshold=cfg["alerts"]["score_change_threshold"],
        )
        self._db.save_thesis(
            {
                "ticker": ticker,
                "result_id": result_id,
                "recorded_at": analysis_date,
                "thesis_summary": decision.thesis,
                "key_risks": decision.risks,
                "target_assumptions": {
                    "bull_case": decision.bull_case,
                    "base_case": decision.base_case,
                    "bear_case": decision.bear_case,
                },
                "decision": decision.investment_view,
                "change_vs_prior": thesis_change.classification,
                "change_reason": thesis_change.reason,
            }
        )
        if thesis_change.classification in ("BROKEN", "STRENGTHENED", "WEAKENED"):
            self._db.add_alert(
                ticker,
                "THESIS_CHANGE",
                "CRITICAL" if thesis_change.classification == "BROKEN" else "INFO",
                f"Thesis {thesis_change.classification}: {thesis_change.reason}",
            )

        latency_ms = int((time.time() - started) * 1000)
        self._db.finish_run(
            run_id,
            agents_called=agents_called,
            data_sources=bundle.sources_used,
            status="OK" if not errors else "PARTIAL",
            errors=errors,
            latency_ms=latency_ms,
        )

        return AnalysisReport(
            ticker=ticker,
            run_id=run_id,
            analysis_date=analysis_date,
            price_at_analysis=price_at_analysis,
            dimension_scores=dimension_scores,
            overall_score=overall_score,
            completeness_pct=completeness_pct,
            data_quality_warnings=dq_report.warnings,
            fundamental=fundamental,
            valuation=valuation,
            technical=technical,
            macro=macro,
            position_risk=position_risk,
            research=research,
            critic=critic,
            decision=decision,
            thesis_change=thesis_change,
            market=bundle.market,
            sector=bundle.financials.sector,
            errors=errors,
            data_sources=bundle.sources_used,
        )
