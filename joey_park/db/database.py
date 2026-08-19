"""Thin SQLite wrapper. No ORM — the schema is small and stable enough that
raw SQL stays more legible than an abstraction over it (see CLAUDE-wide
guidance against premature abstraction).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def new_id() -> str:
    return uuid.uuid4().hex


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        # WAL + busy_timeout: readers don't block writers and concurrent
        # short writes retry instead of raising "database is locked" —
        # needed now that Compare runs analyses in parallel threads.
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert_stock(self, ticker: str, company_name: str | None, sector: str | None, industry: str | None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO stocks (ticker, company_name, sector, industry)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    company_name = excluded.company_name,
                    sector = excluded.sector,
                    industry = excluded.industry
                """,
                (ticker, company_name, sector, industry),
            )

    def set_watchlist(self, ticker: str, on: bool) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE stocks SET watchlist = ? WHERE ticker = ?", (int(on), ticker))

    def get_watchlist(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM stocks WHERE watchlist = 1 ORDER BY ticker").fetchall()

    def start_run(self, ticker: str, model: str, prompt_version: str) -> str:
        run_id = new_id()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs (run_id, ticker, started_at, model, prompt_version, status)
                VALUES (?, ?, datetime('now'), ?, ?, 'RUNNING')
                """,
                (run_id, ticker, model, prompt_version),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        agents_called: list[str],
        data_sources: list[str],
        status: str,
        errors: list[str],
        latency_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE agent_runs SET
                    finished_at = datetime('now'),
                    agents_called = ?,
                    data_sources = ?,
                    status = ?,
                    errors = ?,
                    latency_ms = ?,
                    input_tokens = ?,
                    output_tokens = ?,
                    estimated_cost_usd = ?
                WHERE run_id = ?
                """,
                (
                    json.dumps(agents_called),
                    json.dumps(data_sources),
                    status,
                    json.dumps(errors),
                    latency_ms,
                    input_tokens,
                    output_tokens,
                    estimated_cost_usd,
                    run_id,
                ),
            )

    def save_analysis_result(self, result: dict[str, Any]) -> str:
        result_id = result.get("result_id") or new_id()
        result = {**result, "result_id": result_id}
        json_fields = ("catalysts", "risks", "macro_risk_flags", "data_quality_warnings", "raw_dimension_facts")
        row = {k: (json.dumps(v) if k in json_fields and not isinstance(v, str) else v) for k, v in result.items()}
        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO analysis_results ({columns}) VALUES ({placeholders})",
                tuple(row.values()),
            )
        return result_id

    def get_latest_result(self, ticker: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM analysis_results WHERE ticker = ? ORDER BY analysis_date DESC LIMIT 1",
                (ticker,),
            ).fetchone()

    def get_result_history(self, ticker: str, limit: int = 20) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM analysis_results WHERE ticker = ? ORDER BY analysis_date DESC LIMIT ?",
                (ticker, limit),
            ).fetchall()

    def save_thesis(self, thesis: dict[str, Any]) -> str:
        thesis_id = thesis.get("thesis_id") or new_id()
        thesis = {**thesis, "thesis_id": thesis_id}
        json_fields = ("key_risks", "target_assumptions")
        row = {k: (json.dumps(v) if k in json_fields and not isinstance(v, str) else v) for k, v in thesis.items()}
        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO thesis_history ({columns}) VALUES ({placeholders})",
                tuple(row.values()),
            )
        return thesis_id

    def get_thesis_history(self, ticker: str, limit: int = 10) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM thesis_history WHERE ticker = ? ORDER BY recorded_at DESC LIMIT ?",
                (ticker, limit),
            ).fetchall()

    def add_alert(self, ticker: str, alert_type: str, severity: str, message: str) -> str:
        alert_id = new_id()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO alerts (alert_id, ticker, alert_type, severity, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (alert_id, ticker, alert_type, severity, message),
            )
        return alert_id

    def get_stock(self, ticker: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM stocks WHERE ticker = ?", (ticker,)).fetchone()

    def add_position(self, ticker: str, shares: float, cost_basis: float | None, notes: str | None = None) -> str:
        position_id = new_id()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_positions (position_id, ticker, shares, cost_basis, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (position_id, ticker, shares, cost_basis, notes),
            )
        return position_id

    def close_position(self, position_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE portfolio_positions SET closed_at = datetime('now') WHERE position_id = ?",
                (position_id,),
            )

    def get_open_positions(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM portfolio_positions WHERE closed_at IS NULL").fetchall()

    def get_unacknowledged_alerts(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY created_at DESC"
            ).fetchall()
