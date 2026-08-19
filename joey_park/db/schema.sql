-- Joey Park U.S. Equity Investment Agent — SQLite schema
-- SQLite chosen for a single-user local research tool (docs/DECISION_LOG.md D6).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stocks (
    ticker          TEXT PRIMARY KEY,
    company_name    TEXT,
    sector          TEXT,
    industry        TEXT,
    watchlist       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id          TEXT PRIMARY KEY,
    ticker          TEXT NOT NULL REFERENCES stocks(ticker),
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    agents_called   TEXT,      -- JSON list
    data_sources    TEXT,      -- JSON list
    model           TEXT,
    prompt_version  TEXT,
    status          TEXT NOT NULL DEFAULT 'RUNNING',  -- RUNNING/OK/FAILED
    errors          TEXT,      -- JSON list
    latency_ms      INTEGER,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    estimated_cost_usd REAL
);

CREATE TABLE IF NOT EXISTS analysis_results (
    result_id           TEXT PRIMARY KEY,
    run_id               TEXT NOT NULL REFERENCES agent_runs(run_id),
    ticker                TEXT NOT NULL REFERENCES stocks(ticker),
    analysis_date         TEXT NOT NULL,   -- when the analysis was produced
    price_at_analysis     REAL,
    fundamental_score      REAL,
    growth_score            REAL,
    quality_score            REAL,
    valuation_score           REAL,
    momentum_score             REAL,
    cycle_position_score        REAL,
    catalyst_score                REAL,
    overall_score                 REAL,
    investment_view                TEXT,   -- Bullish/Neutral/Bearish
    confidence                      TEXT,   -- High/Medium/Low
    time_horizon                     TEXT,   -- Short/Medium/Long
    thesis                            TEXT,
    bull_case                          TEXT,
    base_case                           TEXT,
    bear_case                            TEXT,
    valuation_summary                     TEXT,
    catalysts                              TEXT,  -- JSON list
    risks                                   TEXT,  -- JSON list
    what_would_change_my_mind               TEXT,
    macro_risk_flags                         TEXT, -- JSON: {type_a: bool, type_b: bool, type_c: bool, notes: str}
    data_completeness_pct                     REAL,
    data_quality_warnings                      TEXT, -- JSON list
    raw_dimension_facts                         TEXT  -- JSON: full Fact provenance dump
);

CREATE TABLE IF NOT EXISTS thesis_history (
    thesis_id       TEXT PRIMARY KEY,
    ticker          TEXT NOT NULL REFERENCES stocks(ticker),
    result_id       TEXT NOT NULL REFERENCES analysis_results(result_id),
    recorded_at     TEXT NOT NULL,
    thesis_summary  TEXT NOT NULL,
    key_risks       TEXT,            -- JSON list
    target_assumptions TEXT,         -- JSON: {revenue_growth, margin, multiple, ...}
    decision        TEXT,            -- what the user/agent decided to do
    change_vs_prior TEXT,            -- STRENGTHENED/UNCHANGED/WEAKENED/BROKEN/NEW
    change_reason   TEXT
);

CREATE TABLE IF NOT EXISTS portfolio_positions (
    position_id     TEXT PRIMARY KEY,
    ticker          TEXT NOT NULL REFERENCES stocks(ticker),
    shares          REAL NOT NULL,
    cost_basis      REAL,
    opened_at       TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at       TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        TEXT PRIMARY KEY,
    ticker          TEXT NOT NULL REFERENCES stocks(ticker),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    alert_type      TEXT NOT NULL,   -- PRICE_MOVE/SCORE_CHANGE/THESIS_CHANGE/DATA_QUALITY
    severity        TEXT NOT NULL,   -- INFO/WARNING/CRITICAL
    message         TEXT NOT NULL,
    acknowledged    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_analysis_ticker_date ON analysis_results(ticker, analysis_date);
CREATE INDEX IF NOT EXISTS idx_thesis_ticker ON thesis_history(ticker, recorded_at);
CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON alerts(ticker, created_at);
CREATE INDEX IF NOT EXISTS idx_portfolio_open ON portfolio_positions(ticker, closed_at);
