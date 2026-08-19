# Decision Log — Joey Park U.S. Equity Investment Agent

Each entry: the question, the options, the decision, and why — ranked
against the priority order fixed by the spec: accuracy > data reliability >
look-ahead bias prevention > risk control > hallucination prevention >
explainability > maintainability > stability > API cost > speed >
implementation complexity.

---

### D1 — Keep the L×(1−E)×P×T formula, or replace it?

**Options:** (a) keep as the sole score, as all three sources do; (b) drop it
entirely as unscientific; (c) keep it as one configurable input among several
dimension scores, computed deterministically instead of LLM-estimated.

**Decision: (c).** The formula's shape (visibility × risk-adjustment ×
mispricing × structural-position) is a reasonable qualitative frame and
discarding it loses genuinely useful sector intuition the sources encode
(e.g., "physical bottleneck assets get topology premium"). But letting an
LLM eyeball L/E/P/T "from memory" fails the hallucination and evidence-tier
rules outright — every one of those four inputs is either directly
computable from fetched data (L → RPO/backlog growth, revenue growth
acceleration; P → forward multiple vs. history/peers) or is a judgment call
that must cite the specific fact behind it, not be re-invented every run.
`analytics/scoring.py` computes L/E/P/T from `FinancialSnapshot` fields where
a formula exists, and otherwise leaves the field `DATA_NOT_AVAILABLE` rather
than letting the LLM fill the gap.

### D2 — Weekly "run one search prompt by hand" vs. real data pipeline

**Options:** (a) keep Source 3's semi-automated weekly master-prompt
pattern; (b) build a real scheduled fetch against APIs.

**Decision: (b).** A human-triggered chat prompt is not an engineering
artifact this project can ship — it isn't reproducible, has no error
handling, and produces no stored, queryable data. `data/providers/` fetches
from yfinance (price/fundamentals) and SEC EDGAR (official filings/XBRL)
on demand or via a scheduler the user can cron themselves; results are
persisted to SQLite with `retrieval_timestamp` so staleness is checkable.
Ranked #2 (data reliability) over #9 (API cost) and #11 (complexity) — a
reproducible pipeline beats a cheaper manual step.

### D3 — Single composite score vs. structured multi-part Investment View

**Options:** (a) rank tickers by one number, as all sources do; (b) separate
dimension scores + confidence + a structured qualitative decision (Bull/Base/
Bear, thesis, catalysts, risks, invalidation conditions).

**Decision: (b),** per master spec sections 10–13, which explicitly
overrides the sources here (spec section 41 authorizes overriding sources
when they carry hallucination or explainability risk — a single score that
conflates "how good is this business" with "how confident are we" is exactly
that risk). Ranked by #6 (explainability): a portfolio manager needs to know
*why* two tickers with the same score deserve different position sizes.

### D4 — LLM does everything vs. LLM restricted to narrative/verification

**Options:** (a) let the LLM estimate every input, as the sources do; (b)
compute every number that can be computed in Python; use the LLM only to (i)
turn computed facts into a business narrative, (ii) critique that narrative
against the facts, (iii) synthesize the final structured view.

**Decision: (b).** Directly required by master spec sections 13–14
(numbers/narrative/decision separation, hallucination prevention) and D1
above. Also reduces API cost (#9) since deterministic calculation is free
and instant — but that's a side benefit, not the reason; the reason is
correctness and auditability. Every LLM call receives only pre-computed,
sourced numbers in its prompt and is instructed to say `DATA_NOT_AVAILABLE`
/ `LOW_CONFIDENCE` rather than invent a figure; the Critic agent checks this.

### D5 — Point-in-time discipline (look-ahead bias)

**Options:** (a) don't bother, since MVP has no backtester yet; (b) build
`period_date` / `available_date` into the data model from day one.

**Decision: (b).** Ranked #3 in the priority order — deliberately above risk
control and hallucination prevention. Retrofitting point-in-time correctness
after a schema exists is expensive and error-prone (the exact failure mode
the spec warns about), so every fetched fact carries both dates now even
though the MVP's backtester is not built, so that Phase-2 backtesting doesn't
require a data-model rewrite.

### D6 — Database choice

**Options:** Postgres/other server DB vs. SQLite.

**Decision: SQLite.** This is a single-user local research tool, not a
multi-tenant service — spinning up a database server adds operational
surface (#8 stability, #11 complexity) with no accuracy or reliability
benefit for this use case. `db/schema.sql` is plain SQL and portable to
Postgres later if the user ever needs concurrent multi-user access.

### D7 — UI framework

**Options:** React/FastAPI split app vs. a single-process Streamlit
dashboard.

**Decision: Streamlit.** The spec (section 32) explicitly warns against a
"Bloomberg clone" and asks for a prioritized, decision-focused interface,
not a maximal one. A single-process Python dashboard reaches that with far
less surface area than a separate frontend build, and every view (Watchlist,
Stock Research, Compare, Portfolio, Thesis, Alerts, Reports) is a data table
or chart — Streamlit's native strength. Flagged as a **Recommended
Enhancement** (not sourced from any of the three documents, which specify no
UI at all).

### D8 — LLM provider

**Options:** hard-code Anthropic vs. build a provider abstraction.

**Decision: both** — `llm/base.py` defines a minimal `LLMProvider`
interface (`complete(prompt, system, ...) -> str`); `llm/anthropic_provider.py`
is the only concrete implementation shipped, per spec section 27 ("first
implementation may default to one provider"). The user confirmed an
Anthropic API key will be supplied; `.env.example` documents `ANTHROPIC_API_KEY`
and `ANTHROPIC_MODEL`.

### D9 — Data source tier for MVP

**Options:** paid data vendor (FMP/Polygon/Tiingo) vs. free/public sources
only.

**Decision: free/public only for MVP** (user's explicit choice). SEC EDGAR
(official filer data, Tier 1) + yfinance (Tier 2, unofficial but widely used,
free) cover price, fundamentals, and filings without a paid key. News and
macro (FRED) are wired as **optional** providers that degrade to
`DATA_NOT_AVAILABLE` if no key is configured, rather than being required —
documented as a P1 upgrade path in the README, not silently faked.

### D10 — Backtesting

**Decision: not built in the MVP.** No source contains a backtest design to
adapt, and building one correctly (point-in-time data, survivorship-bias-free
universes, transaction costs) on free data sources within this scope would
either be fake (using today's static universe against history) or
undersized to be trustworthy. Shipping a backtester that quietly violates
look-ahead-bias rules would be worse than not shipping one — logged as a P2
limitation, not attempted.
