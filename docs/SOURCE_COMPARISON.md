# Source Comparison — Joey Park U.S. Equity Investment Agent

## 0. Provenance note

The original request named four source documents ("Source 1–4"), delivered as
`share.gemini.google` links. All four links resolved but rendered an empty
body behind a Google login wall — no conversation content was retrievable in
this environment. The user supplied three local files instead, which are
treated here as the working source set. **No fourth document was ever
received or substituted** — this is a known gap, not a fabricated stand-in.
Nothing in this document or the resulting build should be read as describing
a "Source 4."

| # | File | Internal project name used in the file |
|---|------|------------------------------------------|
| Source 1 | `주식 Agent 참고.txt` | "Plan G AI 인프라 사이클 통합 투자 프레임워크" |
| Source 2 | `SH Equity Agent_ AI 인프라 사이클 정량 분석 및 자산 통합 포트폴리오.docx` | "SH Equity Agent (v2.0)" |
| Source 3 | `SH Equity Agent (AI Infra Investment Engine v3.5) 종합 구축 및 고도화 보고서.docx` | "SH Equity Agent (v3.5)" |

Unlike the scenario the master prompt anticipates (four independently
architected multi-agent systems to reconcile), these three documents are
**successive iterations of one lineage**: a single quantitative scoring
formula and system prompt, refined across versions. There is very little
architectural conflict between them — mostly addition and refinement. The
comparison below reflects that reality rather than forcing artificial
disagreement.

## 1. What each source actually contains

### A. Investment philosophy
All three: sector-rotation / cycle-tracking philosophy — AI capex converting
into monetizable, defensible cash flow across three layers (semiconductors →
AI software/cloud → power infrastructure). No stated holding period, no
explicit buy/hold/sell rules beyond score thresholds and "trigger" price/event
levels per ticker. No explicit position sizing or stop-loss methodology.

### B. Agent architecture
None of the three describe a multi-agent system. All three are a **single
system-prompt persona** ("Plan G" / "SH Equity Agent") that, given a ticker,
estimates four variables from context/web search and outputs one templated
block. No orchestrator, no separate research/critic/verification roles, no
memory beyond "compare to last time" being implied but never implemented, no
tool-use framework, no explicit data pipeline — data acquisition is "the LLM
searches the web when asked."

### C. Data
- Source 3 is the most developed: an explicit list of **11 weekly-tracked
  indicators** (earnings/guidance, SEC 8-K, credit spreads, grid
  interconnection queues, NRC approvals, hyperscaler ASIC roadmaps, export
  controls, AI ROI/monetization signals, aggregate capex revisions, memory
  ASP/inventory) and a "semi-automated weekly master search prompt" as the
  sync mechanism (no real scheduler/cron — a human runs one prompt weekly).
- No source distinguishes data tiers, records retrieval timestamps, or
  separates `period_date` from `available_date`. Numbers in the tables
  (revenue growth %, margins, RPO, FCF) are presented without citations or
  observation dates.

### D. Analysis
A single composite formula stands in for fundamental, valuation, and
technical analysis:

```
Score(X) = L × (1 − E) × P × T
  L = Lead-Time  (backlog/RPO visibility, production-readiness lead)
  E = Error/Risk (probability of thesis-breaking failure)
  P = Pricing    (how much of the visible cash flow is already priced in)
  T = Topology   (structural/monopoly position in the value chain)
```

Sector-specific rubrics for L/E/P/T exist for three sectors (Semiconductor,
AI Software & Cloud, Power Infrastructure) in Source 1, expanded to six
sectors with entry-filter business-model criteria and ~180-ticker pools in
Source 3. A parallel "Stage 1–5" asset-transformation-cycle label is also
requested per ticker but never formally defined (which businesses map to
which stage is left to the LLM's judgment each time).

Macro risk is classified into three types, consistently across all three
documents:
- **Type A (전제붕괴 / thesis-collapse):** aggregate hyperscaler AI capex cut
- **Type B (내부재편 / internal reshuffling):** margin compression from
  yield-parity or in-house chip substitution
- **Type C (자기잠식 / self-erosion):** debt-funded capex hurt by rising
  credit spreads

### E. Investment decision
Output is a single composite score per ticker, ranked into a table, plus an
"entry/exit trigger" (usually a valuation band or named event). No Buy/Hold/
Sell taxonomy, no confidence separate from score, no bull/base/bear
scenarios, no explicit "what would change my mind."

### F. Portfolio
Source 2 assembles a 7-sector, ~102-ticker allocation table with suggested
target weights (e.g., "CEG 15%, MSFT 15%, NOW 10%..."), and one systemic
invalidation rule (Type A macro trigger → liquidate across the board). No
correlation, beta, drawdown, or factor-exposure analysis; no per-position
sizing logic beyond the top-10 weights being stated directly.

### G. UX / output
Plain templated text answers in a chat interface. No dashboard, no
persistence beyond the chat history, no alerting.

### H. Engineering
None. These are prompt-engineering artifacts (a "Gem" persona + one-shot
system prompt), not software. No language, framework, database, scheduler,
secrets handling, or tests exist in any source.

## 2. Requirement comparison matrix

| Feature | Src 1 | Src 2 | Src 3 | Classification | Final decision |
|---|---|---|---|---|---|
| L×(1−E)×P×T scoring formula | ✓ (3 sectors) | ✓ (same) | ✓ (6 sectors) | Duplicate | **Adopt**, reframed as one configurable input to a multi-dimension score (not the sole score) — see Decision Log D1 |
| Stage 1–5 transformation-cycle label | ✓ (unlabeled) | ✓ (unlabeled) | ✓ (unlabeled) | Duplicate, underspecified | **Adopt as a descriptive tag only**, not a scored variable, since it was never operationally defined in any source |
| Type A/B/C macro risk taxonomy | ✓ | ✓ | ✓ | Duplicate | **Adopt as-is** — genuinely useful, sector-agnostic, cheap to compute |
| Sector entry-filter business-model criteria | — | partial | ✓ (6 sectors, ~180 tickers) | Unique to Src 3 | **Adopt**, ported into `config/sector_universe.yaml` |
| 11 weekly indicators + semi-automated sync prompt | — | — | ✓ | Unique to Src 3 | **Adopt the indicator list**; **reject the "human runs a weekly search prompt" mechanism** — replaced with real scheduled data pulls from SEC EDGAR / market data APIs (see Decision Log D2) |
| Single LLM persona estimates L/E/P/T from memory/search, no cited source | ✓ | ✓ | ✓ | Conflicts with master-spec hallucination/evidence rules | **Rejected as designed.** Replaced with deterministic calculation from fetched data wherever a number can be computed; LLM is restricted to narrative synthesis over pre-computed, sourced numbers |
| Composite single score as the whole verdict | ✓ | ✓ | ✓ | Conflicts with master-spec "don't compress everything into one score" | **Rejected as sole output.** Kept as one optional sub-score; final output is a structured Investment View (Bull/Base/Bear, confidence, thesis, risks, invalidation conditions) |
| Portfolio target-weight table | — | ✓ | — | Unique to Src 2 | **Adopt the concept** (portfolio construction view); **reject the fixed weights** — hardcoded percentages are sample data, not a generalizable allocation engine |
| Point-in-time data discipline / look-ahead bias controls | — | — | — | Missing from all sources | **Added** (not in any source) — required by master spec section 7; flagged explicitly as a Recommended Enhancement, not attributed to any source |
| Data-quality gate / validation | — | — | — | Missing from all sources | **Added** — master spec section 15 |
| Critic/verification pass before final decision | — | — | — | Missing from all sources | **Added** — master spec section 21 |
| Thesis memory / change detection over time | implied ("이전 판단 대비") but not built | — | — | Unique intent, never implemented | **Adopt the intent, build the implementation** |
| Backtesting | — | — | — | Missing from all sources | **Not built in MVP** — no historical point-in-time dataset is available from free sources; documented as a P2 limitation rather than faked |
| Naming: "Plan G" / "SH Equity Agent" family | ✓ / — | — / ✓ | — / ✓ | N/A — branding | **Removed entirely**, replaced with "Joey Park U.S. Equity Investment Agent" per the absolute naming rule |

## 3. What was deduplicated

The three sources overlap by roughly 70% (same formula, same macro-risk
taxonomy, same output template shape). Source 3 strictly a superset of
Source 1 on sector coverage and adds the weekly-indicator list; Source 2's
distinct contribution is the cross-sector allocation table and the SNOW/CRM/
NOW and SK하이닉스/NAVER/HD현대일렉트릭 worked examples. These were merged
into one canonical spec rather than kept as parallel systems.

## 4. What was judged unnecessary and dropped

- **Per-ticker hardcoded L/E/P/T values** (e.g. "NVDA: L=0.95, E=0.20...") —
  these are point-in-time analyst judgments frozen at the document's
  writing date (2026-05/2026-08). Hardcoding them into the shipped system
  would silently go stale and violates the master spec's Tier-4/hallucination
  rules (a number with no recomputation path is indistinguishable from a
  guess after enough time passes). They are preserved only as illustrative
  fixtures in tests, clearly marked as sample data with their original date.
- **The ~102–180 ticker "universe pool" as a hardcoded stock-picking
  whitelist** — kept as a *configurable, editable* sector-mapping file
  (`config/sector_universe.yaml`) rather than logic baked into code, since
  sector membership and business-model filters are exactly the kind of
  judgment call that changes over time and shouldn't require a code change.
- **The "3 candidate rebrand names" discussion in Source 3** — moot; the
  naming rule supersedes all of it.
