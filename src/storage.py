"""本地 SQLite 审核记录与审计事件。"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

from .models import ReviewSession, dumps_json, now_iso
from .constants import is_public_deployment


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def default_database_path() -> Path:
    configured = os.environ.get("XRAY_DATA_DIR", "").strip()
    if configured:
        runtime_dir = Path(configured)
    elif is_public_deployment():
        runtime_dir = Path(tempfile.gettempdir()) / "chuanbo-xray"
    else:
        runtime_dir = Path(configured) if configured else PROJECT_ROOT / "data" / "runtime"
        if not runtime_dir.is_absolute():
            runtime_dir = PROJECT_ROOT / runtime_dir
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / "chuanbo_xray.sqlite3"


class ReviewStore:
    def __init__(self, database_path: str | Path | None = None):
        self.database_path = Path(database_path) if database_path else default_database_path()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    run_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    is_synthetic INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_run_id ON audit_events(run_id);
                """
            )

    def save_review(
        self,
        session: ReviewSession,
        *,
        action: str = "analysis_saved",
        actor: str = "system",
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = dumps_json(session.to_dict(), indent=2)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reviews (run_id, title, created_at, mode, is_synthetic, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    title=excluded.title,
                    mode=excluded.mode,
                    is_synthetic=excluded.is_synthetic,
                    payload_json=excluded.payload_json
                """,
                (session.run_id, session.title, session.created_at, session.mode, int(session.is_synthetic), payload),
            )
        self.add_event(session.run_id, action, actor, details or {})

    def add_event(self, run_id: str, action: str, actor: str, details: dict[str, Any] | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO audit_events (run_id, timestamp, action, actor, details_json) VALUES (?, ?, ?, ?, ?)",
                (run_id, now_iso(), action, actor or "未填写", dumps_json(details or {}, indent=0)),
            )

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_id, run_id, timestamp, action, actor, details_json FROM audit_events WHERE run_id=? ORDER BY event_id ASC",
                (run_id,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "event_id": row["event_id"],
                    "run_id": row["run_id"],
                    "timestamp": row["timestamp"],
                    "action": row["action"],
                    "actor": row["actor"],
                    "details_json": row["details_json"],
                }
            )
        return events

    def list_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id, title, created_at, mode, is_synthetic FROM reviews ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
