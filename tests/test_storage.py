"""Step 1 (v2) test cases from PLANNING.md: SQLite storage layer."""

from datetime import datetime

import pytest

from backspace_tracker.counter import Category, Counter
from backspace_tracker.storage import Storage


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


def test_session_with_no_app_counts_loads_empty_breakdown(storage):
    # Direct compute path: a stats object with no per-app data at all.
    from backspace_tracker.counter import compute_stats

    stats = compute_stats({Category.BACKSPACE: 1}, duration_seconds=10.0)
    storage.save_session(datetime(2026, 6, 6, 9, 0), stats)
    [record] = storage.load_sessions()
    assert record.stats.app_counts == {}
    assert record.stats.counts[Category.BACKSPACE] == 1