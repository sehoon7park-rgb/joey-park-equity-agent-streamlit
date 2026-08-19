# Joey Park U.S. Equity Investment Agent

An evidence-driven U.S. equity research and decision-tracking tool: point a
ticker at it and get a structured Investment View (Bull/Base/Bear, explicit
confidence, thesis, catalysts, risks, and "what would change my mind") built
from real fetched data — not an LLM's unsourced impression of the company.

See [`docs/SOURCE_COMPARISON.md`](docs/SOURCE_COMPARISON.md) and
[`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) for how this was designed:
what came from the source material, what was dropped, and why.

## Design in one picture

```
Ticker
  -> Data Agent            (yfinance + SEC EDGAR, free, sourced facts only)
  -> Data Quality Gate      (staleness / completeness / sanity checks)
  -> Fundamental / Valuation / Technical / Macro / Risk Agents
     (all deterministic Python — every number traces to a fetched Fact)
  -> Research Agent (LLM)   (narrative from facts only, no invented numbers)
  -> Critic Agent (LLM)     (checks the narrative against the facts)
  -> Decision Agent (LLM)   (Bull/Base/Bear + confidence, separate from score)
  -> Thesis Tracker         (what changed since the last run on this ticker)
  -> SQLite + Markdown report
```

Numbers, narrative, and decision are kept in visibly separate layers
throughout — see any generated report.

## Quickstart

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY and SEC_EDGAR_CONTACT_EMAIL at minimum

python -m joey_park.cli analyze MSFT
```

Without `ANTHROPIC_API_KEY` set, the quantitative dimension scores and
valuation table still compute normally (they're pure Python over free data);
the Research/Critic/Decision sections will show `DATA_NOT_AVAILABLE`
placeholders instead of a real Investment View.

### Dashboard

```bash
streamlit run ui/app.py
```

Views: Watchlist, Stock Research, Compare, Portfolio, Thesis, Alerts,
Reports (master-spec section 32).

### Tests

```bash
pytest tests/ -v
```

39 tests: scoring, valuation, data validation, thesis-change detection, and
integration tests that run the full pipeline against a mocked LLM and mocked
data provider (including LLM-outage and sparse-data failure modes).

## Language

The UI and all LLM-generated narrative content (thesis, scenarios,
catalysts, risks, critic findings) are Korean, aimed at Korean-speaking
users — see the agent system prompts in `joey_park/agents/research_agent.py`,
`critic_agent.py`, `decision_agent.py` for the exact language contract:
JSON keys and controlled-vocabulary enum values (`Bullish`/`Neutral`/
`Bearish`, `High`/`Medium`/`Low`, etc.) always stay in English so the code
that reads them doesn't break; only free-text values are Korean. Swapping
to another display language means editing those three prompts (and the
`*_KR` maps in `ui/app.py` / `report.py`) — nothing in the data/scoring
layer needs to change.

## Configuration

- [`joey_park/config/config.yaml`](joey_park/config/config.yaml) — scoring
  weights, valuation method-by-sector, position/sector limits, staleness
  thresholds, per-agent enable/disable.
- [`joey_park/config/sector_universe.yaml`](joey_park/config/sector_universe.yaml)
  — starter watchlist by sector with entry-filter notes and the structural
  "topology" weight (see Decision Log D1). Edit freely; nothing in code
  depends on this list being complete or fixed.
- `.env` — API keys and paths. See `.env.example` for every variable.

## What's implemented vs. not (be honest about this before relying on it)

**Working:**
- Full ticker -> report pipeline against live free data (yfinance + SEC
  EDGAR); verified against real tickers, not just mocks.
- Deterministic dimension scoring (Fundamental/Growth/Quality/Valuation/
  Momentum/Cycle-Position) with confidence separated from score.
- Multi-method, sector-aware valuation.
- Data Quality Gate (staleness, completeness, sanity bounds, frozen-feed
  detection).
- Three-stage LLM pipeline (Research -> Critic -> Decision) with graceful
  degradation on missing config or provider outage — verified by test.
- Thesis change detection across repeated runs (NEW/STRENGTHENED/UNCHANGED/
  WEAKENED/BROKEN) persisted to SQLite.
- Streamlit dashboard covering all seven planned views, including a
  portfolio position add/close form (backed by `add_position`/
  `close_position`/`get_open_positions` in `db/database.py`).
- Point-in-time data model (`period_date` vs. `available_date` on every
  fact) — ready for backtesting even though no backtester exists yet.
- Korean-language UI and LLM narrative output, verified end-to-end against
  live tickers (see `docs/SAMPLE_REPORT.md`) — including catching and fixing
  a real bug where Korean output tripped `max_tokens` limits sized for
  English and silently misreported as `DATA_NOT_AVAILABLE` instead of the
  actual truncation; `stop_reason` is now checked to tell the two apart.

**Partial:**
- Macro risk taxonomy: Type C (credit-spread/leverage) is real and
  data-backed. Type A (aggregate hyperscaler capex direction) and Type B
  (yield-parity/in-house chip substitution) have no free structured data
  source, so they're always `DATA_NOT_AVAILABLE` from the Macro Agent and
  are left to the Research/Critic agents to reason about qualitatively from
  SEC filings — they do not currently pull filing text, only filing
  metadata (form/date), so this reasoning is presently thin.
- News/Catalyst coverage: `NEWS_API_KEY` is wired but no provider is
  implemented yet (disabled by default in config.yaml) — catalysts today
  come only from the LLM's narrative + SEC filing *metadata*, not headlines.

**Not implemented (P2, see Decision Log D10):**
- Backtesting. No source document had a valid design to adapt, and a
  correct one (point-in-time, survivorship-bias-free, with transaction
  costs) wasn't achievable on free data within this scope. Shipping a fake
  one would violate the project's own look-ahead-bias rules, so it was
  deliberately left out rather than faked.
- Peer-relative valuation (multiples are compared to fixed heuristic bands,
  not a live peer set — see `config.yaml valuation.heuristics`).
- Correlation/factor-exposure analysis in the Portfolio Agent.

## Priority for next work (P0/P1/P2)

- **P1:** A real news provider; SEC 8-K/10-Q *text* extraction (not just
  metadata) so Type A/B macro reasoning has something concrete to work from.
- **P1:** Live peer-set valuation instead of static heuristic bands.
- **P2:** Backtesting with a point-in-time data snapshot strategy.
- **P2:** ROIC (needs an invested-capital calculation yfinance doesn't
  expose directly).
- **P2:** Correlation/factor-exposure analysis in the Portfolio Agent
  (current portfolio math covers concentration/sector exposure only).

## Repository structure

```
joey_park/
  config/       settings.py, config.yaml, sector_universe.yaml
  data/         models.py, validation.py, providers/ (yfinance, SEC EDGAR, FRED)
  db/           schema.sql, database.py
  llm/          base.py (provider interface), anthropic_provider.py
  analytics/    scoring.py, valuation_methods.py  (all deterministic)
  agents/       data/fundamental/valuation/technical/macro/risk/
                research/critic/decision/portfolio agents + orchestrator.py
  memory/       thesis_tracker.py
  cli.py, report.py, bootstrap.py
ui/app.py       Streamlit dashboard
tests/          unit + integration + failure-mode tests
docs/           SOURCE_COMPARISON.md, DECISION_LOG.md
```

## A note on the two docs/ files

`docs/SOURCE_COMPARISON.md` and `docs/DECISION_LOG.md` are the only two
files in this repository that reference the prior project names the source
material used. That is intentional and required — see the "Provenance"
section of SOURCE_COMPARISON.md — audit trail, not branding. Every other
file in this repository (code, config, README, prompts, UI strings, test
fixtures) uses only "Joey Park" naming; the repository was swept
case-insensitively to confirm this.
