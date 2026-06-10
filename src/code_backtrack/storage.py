"""SQLite session persistence. Only aggregate counts and timestamps - never keys.

Connections are opened per operation: saves happen on the listener callback
thread while the Storage object is created on the main thread, and sqlite3
connections must not cross threads.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .counter import Category, SessionStats, compute_stats

# Column per category, in enum order: backspace, ctrl_backspace, delete, ...
# ("delete" is an SQL keyword, so all count columns are double-quoted.)
_COUNT_COLUMNS = [cat.value for cat in Category]
_QUOTED = ", ".join(f'"{col}"' for col in _COUNT_COLUMNS)
_PLACEHOLDERS = ", ".join("?" for _ in _COUNT_COLUMNS)
_COUNT_DDL = ", ".join(f'"{col}" INTEGER NOT NULL' for col in _COUNT_COLUMNS)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    {_COUNT_DDL}
);
CREATE TABLE IF NOT EXISTS app_counts (
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    app TEXT NOT NULL,
    {_COUNT_DDL},
    PRIMARY KEY (session_id, app)
);
"""


def default_db_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "code-backtrack" / "sessions.db"


@dataclass(frozen=True)
class SessionRecord:
    id: int
    started_at: str  # ISO 8601
    stats: SessionStats


class Storage:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            self._add_missing_count_columns(conn)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _add_missing_count_columns(conn: sqlite3.Connection) -> None:
        """Backfill count columns added in later versions (e.g. v2.5 overtype,
        cut) onto a pre-existing DB. New columns default to 0 so old sessions
        load unchanged."""
        for table in ("sessions", "app_counts"):
            existing = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
            for col in _COUNT_COLUMNS:
                if col not in existing:
                    conn.execute(
                        f'ALTER TABLE "{table}" ADD COLUMN "{col}" INTEGER NOT NULL DEFAULT 0'
                    )

    def save_session(self, started_at: datetime, stats: SessionStats) -> int:
        """Persist one finished session; returns its id."""
        counts_row = [stats.counts[cat] for cat in Category]
        with self._connect() as conn:
            cur = conn.execute(
                f"INSERT INTO sessions (started_at, duration_seconds, {_QUOTED}) "
                f"VALUES (?, ?, {_PLACEHOLDERS})",
                [started_at.isoformat(timespec="seconds"), stats.duration_seconds, *counts_row],
            )
            session_id = cur.lastrowid
            for app, per_app in stats.app_counts.items():
                conn.execute(
                    f"INSERT INTO app_counts (session_id, app, {_QUOTED}) "
                    f"VALUES (?, ?, {_PLACEHOLDERS})",
                    [session_id, app, *(per_app.get(cat, 0) for cat in Category)],
                )
        return session_id

    def delete_session(self, session_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM app_counts WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def delete_all(self) -> int:
        """Remove every session; returns how many were deleted."""
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            conn.execute("DELETE FROM app_counts")
            conn.execute("DELETE FROM sessions")
        return count

    def load_sessions(self) -> list[SessionRecord]:
        """All sessions, ordered by start time."""
        with self._connect() as conn:
            session_rows = conn.execute(
                f"SELECT id, started_at, duration_seconds, {_QUOTED} "
                "FROM sessions ORDER BY started_at, id"
            ).fetchall()
            app_rows = conn.execute(
                f"SELECT session_id, app, {_QUOTED} FROM app_counts"
            ).fetchall()

        apps_by_session: dict[int, dict[str, dict[Category, int]]] = {}
        for session_id, app, *counts in app_rows:
            apps_by_session.setdefault(session_id, {})[app] = dict(
                zip(Category, counts)
            )

        records = []
        for session_id, started_at, duration, *counts in session_rows:
            stats = compute_stats(
                dict(zip(Category, counts)),
                duration,
                apps_by_session.get(session_id, {}),
            )
            records.append(SessionRecord(id=session_id, started_at=started_at, stats=stats))
        return records
