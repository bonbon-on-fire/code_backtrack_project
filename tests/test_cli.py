"""Step 5 (v2) test cases from PLANNING.md: history/apps CLI and renderers."""

from datetime import datetime

from code_backtrack.__main__ import main
from code_backtrack.counter import Category, Counter
from code_backtrack.reporter import NO_SESSIONS_HINT, render_apps, render_history
from code_backtrack.storage import Storage


def make_stats(records, duration=120.0):
    clock_values = iter([0.0, duration])
    counter = Counter(clock=lambda: next(clock_values))
    counter.start()
    for category, app in records:
        counter.record(category, app=app)
    return counter.stop()


def seeded_storage(tmp_path):
    storage = Storage(tmp_path / "sessions.db")
    storage.save_session(
        datetime(2026, 6, 6, 14, 30),
        make_stats(
            [(Category.BACKSPACE, "Code.exe")] * 4
            + [(Category.OTHER, "Code.exe")] * 4
            + [(Category.CTRL_Z, "notepad.exe")] * 2
        ),
    )
    storage.save_session(
        datetime(2026, 6, 7, 9, 0),
        make_stats([(Category.BACKSPACE, "Code.exe"), (Category.OTHER, "chrome.exe")]),
    )
    return storage


def test_render_history_includes_sessions_and_v1_formatting(tmp_path):
    out = render_history(seeded_storage(tmp_path).load_sessions())
    assert "2026-06-06 14:30:00" in out
    assert "2026-06-07 09:00:00" in out
    assert "2m 00s" in out  # v1 duration formatting reused
    assert "60.0%" in out  # session 1: 6 corrections / 10 keys
    assert "3.0/min" in out  # session 1: 6 corrections / 2 min


def test_render_apps_aggregates_across_sessions(tmp_path):
    out = render_apps(seeded_storage(tmp_path).load_sessions())
    # Code.exe: 4+1 corrections of 9 keys across both sessions
    assert "Code.exe" in out
    assert "corr      5" in out
    assert "notepad.exe" in out
    assert "chrome.exe" in out


def test_render_apps_sorted_by_corrections(tmp_path):
    out = render_apps(seeded_storage(tmp_path).load_sessions())
    assert out.index("Code.exe") < out.index("notepad.exe") < out.index("chrome.exe")


def test_empty_db_friendly_message(tmp_path):
    storage = Storage(tmp_path / "fresh.db")
    assert render_history(storage.load_sessions()) == NO_SESSIONS_HINT
    assert render_apps(storage.load_sessions()) == NO_SESSIONS_HINT


def test_cli_history_end_to_end(tmp_path, capsys):
    seeded_storage(tmp_path)
    main(["history", "--db", str(tmp_path / "sessions.db")])
    out = capsys.readouterr().out
    assert "Session history" in out
    assert "2026-06-06 14:30:00" in out


def test_cli_apps_end_to_end(tmp_path, capsys):
    seeded_storage(tmp_path)
    main(["apps", "--db", str(tmp_path / "sessions.db")])
    assert "Code.exe" in capsys.readouterr().out


def test_cli_list_shows_all_sessions(tmp_path, capsys):
    seeded_storage(tmp_path)
    main(["list", "--db", str(tmp_path / "sessions.db")])
    out = capsys.readouterr().out
    assert "2026-06-06 14:30:00" in out
    assert "2026-06-07 09:00:00" in out
    assert "2 sessions" in out


def test_cli_delete_by_exact_datetime(tmp_path, capsys):
    storage = seeded_storage(tmp_path)
    main(["delete", "2026-06-06", "14:30:00", "--db", str(tmp_path / "sessions.db")])
    assert "deleted session 2026-06-06 14:30:00" in capsys.readouterr().out
    remaining = storage.load_sessions()
    assert [r.started_at for r in remaining] == ["2026-06-07T09:00:00"]


def test_cli_delete_by_prefix(tmp_path, capsys):
    storage = seeded_storage(tmp_path)
    main(["delete", "2026-06-07", "--db", str(tmp_path / "sessions.db")])
    assert "deleted session 2026-06-07 09:00:00" in capsys.readouterr().out
    assert len(storage.load_sessions()) == 1


def test_cli_delete_ambiguous_prefix_refuses(tmp_path, capsys):
    storage = seeded_storage(tmp_path)
    main(["delete", "2026-06", "--db", str(tmp_path / "sessions.db")])
    out = capsys.readouterr().out
    assert "matches 2 sessions" in out
    assert len(storage.load_sessions()) == 2  # nothing deleted


def test_cli_delete_not_found(tmp_path, capsys):
    storage = seeded_storage(tmp_path)
    main(["delete", "2030-01-01", "--db", str(tmp_path / "sessions.db")])
    assert "no session starting with" in capsys.readouterr().out
    assert len(storage.load_sessions()) == 2


def test_cli_delete_all(tmp_path, capsys):
    storage = seeded_storage(tmp_path)
    main(["delete", "--all", "--db", str(tmp_path / "sessions.db")])
    assert "deleted 2 sessions" in capsys.readouterr().out
    assert storage.load_sessions() == []


def test_cli_delete_without_args_explains(tmp_path, capsys):
    seeded_storage(tmp_path)
    main(["delete", "--db", str(tmp_path / "sessions.db")])
    out = capsys.readouterr().out
    assert "--all" in out  # usage hint, nothing deleted


def test_delete_removes_app_rows_too(tmp_path):
    storage = seeded_storage(tmp_path)
    first = storage.load_sessions()[0]
    storage.delete_session(first.id)
    import sqlite3

    with sqlite3.connect(tmp_path / "sessions.db") as conn:
        orphans = conn.execute(
            "SELECT COUNT(*) FROM app_counts WHERE session_id = ?", (first.id,)
        ).fetchone()[0]
    assert orphans == 0


def test_bare_invocation_runs_tracker(monkeypatch):
    import code_backtrack.app as app_module

    called = []
    monkeypatch.setattr(app_module, "run", lambda: called.append(True))
    main([])
    assert called == [True]
