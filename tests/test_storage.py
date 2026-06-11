"""Step 1 (v2) test cases from PLANNING.md: SQLite storage layer."""

from datetime import datetime

import pytest

from code_backtrack.counter import Category, Counter
from code_backtrack.storage import Storage


def make_stats(records, duration=60.0):
    """records: list of (category, app) tuples."""
    clock_values = iter([0.0, duration])
    counter = Counter(clock=lambda: next(clock_values))
    counter.start()
    for category, app in records:
        counter.record(category, app=app)
    return counter.stop()


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "sessions.db")


def test_save_load_round_trip_preserves_every_count(storage):
    stats = make_stats(
        [
            (Category.BACKSPACE, "Code.exe"),
            (Category.BACKSPACE, "Code.exe"),
            (Category.CTRL_BACKSPACE, "Code.exe"),
            (Category.DELETE, "notepad.exe"),
            (Category.CTRL_DELETE, "notepad.exe"),
            (Category.CTRL_Z, "Code.exe"),
            (Category.OTHER, "chrome.exe"),
        ],
        duration=90.0,
    )
    storage.save_session(datetime(2026, 6, 6, 14, 30), stats)

    [record] = storage.load_sessions()
    assert record.stats.counts == stats.counts
    assert record.stats.app_counts == stats.app_counts
    assert record.stats.duration_seconds == pytest.approx(90.0)
    assert record.stats.correction_ratio == pytest.approx(stats.correction_ratio)
    assert record.started_at == "2026-06-06T14:30:00"


def test_schema_auto_created_on_fresh_db(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "sessions.db"
    storage = Storage(db_path)  # parent dirs + schema created here
    assert db_path.exists()
    assert storage.load_sessions() == []


def test_multiple_sessions_ordered_by_start_time(storage):
    later = make_stats([(Category.BACKSPACE, "Code.exe")])
    earlier = make_stats([(Category.DELETE, "notepad.exe")])
    storage.save_session(datetime(2026, 6, 6, 15, 0), later)
    storage.save_session(datetime(2026, 6, 6, 9, 0), earlier)

    records = storage.load_sessions()
    assert [r.started_at for r in records] == ["2026-06-06T09:00:00", "2026-06-06T15:00:00"]


def test_app_rows_linked_to_right_session(storage):
    first = make_stats([(Category.BACKSPACE, "Code.exe")])
    second = make_stats([(Category.BACKSPACE, "notepad.exe")])
    storage.save_session(datetime(2026, 6, 6, 9, 0), first)
    storage.save_session(datetime(2026, 6, 6, 10, 0), second)

    rec1, rec2 = storage.load_sessions()
    assert set(rec1.stats.app_counts) == {"Code.exe"}
    assert set(rec2.stats.app_counts) == {"notepad.exe"}


def test_save_returns_distinct_incrementing_ids(storage):
    stats = make_stats([(Category.BACKSPACE, "Code.exe")])
    id1 = storage.save_session(datetime(2026, 6, 6, 9, 0), stats)
    id2 = storage.save_session(datetime(2026, 6, 6, 10, 0), stats)
    assert id2 > id1


def test_overtype_and_cut_counts_round_trip(storage):
    stats = make_stats(
        [
            (Category.OVERTYPE, "Code.exe"),
            (Category.OVERTYPE, "Code.exe"),
            (Category.CUT, "notepad.exe"),
        ]
    )
    storage.save_session(datetime(2026, 6, 8, 12, 0), stats)
    [record] = storage.load_sessions()
    assert record.stats.counts[Category.OVERTYPE] == 2
    assert record.stats.counts[Category.CUT] == 1
    assert record.stats.app_counts["Code.exe"][Category.OVERTYPE] == 2
    assert record.stats.app_counts["notepad.exe"][Category.CUT] == 1


def test_old_db_without_v25_columns_migrates_and_loads(tmp_path):
    import sqlite3

    # Build a pre-v2.5 DB by hand: original columns only, no overtype/cut.
    db_path = tmp_path / "old.db"
    legacy_cols = ["backspace", "ctrl_backspace", "delete", "ctrl_delete", "ctrl_z", "other"]
    quoted = ", ".join(f'"{c}"' for c in legacy_cols)
    ddl = ", ".join(f'"{c}" INTEGER NOT NULL' for c in legacy_cols)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            f"started_at TEXT NOT NULL, duration_seconds REAL NOT NULL, {ddl})"
        )
        conn.execute(
            f"CREATE TABLE app_counts (session_id INTEGER NOT NULL, app TEXT NOT NULL, "
            f"{ddl}, PRIMARY KEY (session_id, app))"
        )
        conn.execute(
            f"INSERT INTO sessions (started_at, duration_seconds, {quoted}) "
            f"VALUES ('2026-06-01T10:00:00', 30.0, 4, 0, 0, 0, 0, 11)"
        )

    storage = Storage(db_path)  # opening must migrate, not crash
    [record] = storage.load_sessions()
    assert record.stats.counts[Category.BACKSPACE] == 4
    assert record.stats.counts[Category.OVERTYPE] == 0  # backfilled default
    assert record.stats.counts[Category.CUT] == 0
    # and a new session with v2.5 counts saves fine into the migrated DB
    storage.save_session(datetime(2026, 6, 8, 9, 0), make_stats([(Category.CUT, "Code.exe")]))
    assert len(storage.load_sessions()) == 2


# --- v3 test cases from PLANNING.md: char column + migration ---


def test_char_count_round_trips(storage):
    stats = make_stats(
        [
            (Category.CHAR, "Code.exe"),
            (Category.CHAR, "Code.exe"),
            (Category.CHAR, "Code.exe"),
            (Category.BACKSPACE, "Code.exe"),
        ]
    )
    storage.save_session(datetime(2026, 6, 9, 11, 0), stats)
    [record] = storage.load_sessions()
    assert record.stats.counts[Category.CHAR] == 3
    assert record.stats.app_counts["Code.exe"][Category.CHAR] == 3
    # derived char stats survive the round-trip
    assert record.stats.chars_added == 3
    assert record.stats.chars_deleted == 1
    assert record.stats.delete_pct == pytest.approx(1 / 3)


def test_old_db_without_char_column_migrates_and_loads(tmp_path):
    import sqlite3

    # Pre-v3 DB: has the v2.5 columns (overtype/cut) but no "char" column yet.
    db_path = tmp_path / "pre_v3.db"
    cols = [
        "backspace", "ctrl_backspace", "delete", "ctrl_delete",
        "ctrl_z", "overtype", "cut", "other",
    ]
    quoted = ", ".join(f'"{c}"' for c in cols)
    ddl = ", ".join(f'"{c}" INTEGER NOT NULL' for c in cols)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            f"started_at TEXT NOT NULL, duration_seconds REAL NOT NULL, {ddl})"
        )
        conn.execute(
            f"CREATE TABLE app_counts (session_id INTEGER NOT NULL, app TEXT NOT NULL, "
            f"{ddl}, PRIMARY KEY (session_id, app))"
        )
        conn.execute(
            f"INSERT INTO sessions (started_at, duration_seconds, {quoted}) "
            f"VALUES ('2026-06-01T10:00:00', 30.0, 4, 0, 0, 0, 0, 0, 0, 9)"
        )

    storage = Storage(db_path)  # opening must add the char column, not crash
    [record] = storage.load_sessions()
    assert record.stats.counts[Category.CHAR] == 0  # backfilled default
    assert record.stats.chars_added == 0
    # a new session carrying CHAR counts saves fine into the migrated DB
    storage.save_session(datetime(2026, 6, 9, 9, 0), make_stats([(Category.CHAR, "Code.exe")]))
    rec1, rec2 = storage.load_sessions()
    assert rec2.stats.counts[Category.CHAR] == 1


def test_session_with_no_app_counts_loads_empty_breakdown(storage):
    # Direct compute path: a stats object with no per-app data at all.
    from code_backtrack.counter import compute_stats

    stats = compute_stats({Category.BACKSPACE: 1}, duration_seconds=10.0)
    storage.save_session(datetime(2026, 6, 6, 9, 0), stats)
    [record] = storage.load_sessions()
    assert record.stats.app_counts == {}
    assert record.stats.counts[Category.BACKSPACE] == 1