"""Step 4 test cases from PLANNING.md: live wiring (mocked callbacks)."""

import io
import itertools

import pytest
from pynput import keyboard

from code_backtrack.app import App
from code_backtrack.counter import UNKNOWN_APP, Category

Key = keyboard.Key
KeyCode = keyboard.KeyCode


@pytest.fixture
def out():
    return io.StringIO()


@pytest.fixture
def app(out):
    return App(
        out=out,
        clock=itertools.count(0.0, 1.0).__next__,
        probe=lambda: "TestApp.exe",
    )


def toggle(app):
    """Press and release Ctrl+Alt+B."""
    b = KeyCode.from_char("b")
    app.on_press(Key.ctrl_l)
    app.on_press(Key.alt_l)
    app.on_press(b)
    app.on_release(b)
    app.on_release(Key.alt_l)
    app.on_release(Key.ctrl_l)


def type_key(app, key):
    app.on_press(key)
    app.on_release(key)


def test_events_while_idle_count_nothing(app):
    type_key(app, Key.backspace)
    type_key(app, KeyCode.from_char("a"))
    assert not app.recording
    assert app.last_stats is None


def test_hotkey_starts_then_stops_and_finalizes(app):
    toggle(app)
    assert app.recording
    type_key(app, Key.backspace)
    type_key(app, KeyCode.from_char("a"))
    toggle(app)
    assert not app.recording
    stats = app.last_stats
    assert stats is not None
    assert stats.total_keystrokes == 2
    assert stats.correction_count == 1


def test_hotkey_press_adds_nothing_to_new_session(app):
    toggle(app)  # start
    toggle(app)  # stop immediately: nothing typed in between
    assert app.last_stats.total_keystrokes == 0


def test_second_session_starts_from_zero(app):
    toggle(app)
    type_key(app, Key.backspace)
    toggle(app)
    assert app.last_stats.total_keystrokes == 1

    toggle(app)
    toggle(app)
    assert app.last_stats.total_keystrokes == 0


def test_shutdown_while_recording_finalizes_session(app, out):
    toggle(app)
    type_key(app, Key.backspace)
    app.shutdown()
    assert app.last_stats is not None
    assert app.last_stats.total_keystrokes == 1
    assert "Session summary" in out.getvalue()


def test_shutdown_while_idle_is_clean(app, out):
    app.shutdown()
    assert app.last_stats is None
    assert "Session summary" not in out.getvalue()


def test_summary_printed_on_stop(app, out):
    toggle(app)
    type_key(app, Key.backspace)
    toggle(app)
    assert "Session summary" in out.getvalue()


# --- Step 4 (v2) test cases from PLANNING.md: storage wiring ---


def make_app_with_storage(out, tmp_path, probe=lambda: "TestApp.exe"):
    from code_backtrack.storage import Storage

    storage = Storage(tmp_path / "sessions.db")
    app = App(
        out=out,
        clock=itertools.count(0.0, 1.0).__next__,
        probe=probe,
        storage=storage,
    )
    return app, storage


def test_stop_creates_pending_save_not_a_row(out, tmp_path):
    app, storage = make_app_with_storage(out, tmp_path)
    toggle(app)
    type_key(app, Key.backspace)
    toggle(app)

    assert app.pending_save is not None
    assert storage.load_sessions() == []  # nothing saved until the user answers


def test_confirmed_save_persists_and_reports_datetime(out, tmp_path):
    app, storage = make_app_with_storage(out, tmp_path)
    toggle(app)
    type_key(app, Key.backspace)
    type_key(app, KeyCode.from_char("a"))
    toggle(app)
    app.resolve_pending_save(True)

    [record] = storage.load_sessions()
    assert record.stats.total_keystrokes == 2
    assert record.stats.correction_count == 1
    assert record.stats.app_counts["TestApp.exe"][Category.BACKSPACE] == 1
    assert "saved session 20" in out.getvalue()  # date-time identity, no #N
    assert "#1" not in out.getvalue()
    assert app.pending_save is None


def test_declined_save_discards_session(out, tmp_path):
    app, storage = make_app_with_storage(out, tmp_path)
    toggle(app)
    type_key(app, Key.backspace)
    toggle(app)
    app.resolve_pending_save(False)

    assert storage.load_sessions() == []
    assert "session discarded" in out.getvalue()
    assert app.pending_save is None


def test_probe_failure_still_counts_key(out, tmp_path):
    app, storage = make_app_with_storage(out, tmp_path, probe=lambda: UNKNOWN_APP)
    toggle(app)
    type_key(app, Key.backspace)
    toggle(app)
    app.resolve_pending_save(True)

    [record] = storage.load_sessions()
    assert record.stats.total_keystrokes == 1
    assert record.stats.app_counts[UNKNOWN_APP][Category.BACKSPACE] == 1


def test_shutdown_while_recording_creates_pending_save(out, tmp_path):
    app, storage = make_app_with_storage(out, tmp_path)
    toggle(app)
    type_key(app, Key.backspace)
    app.shutdown()
    assert app.pending_save is not None
    app.resolve_pending_save(True)
    assert len(storage.load_sessions()) == 1


def test_new_session_can_start_while_save_pending(out, tmp_path):
    app, storage = make_app_with_storage(out, tmp_path)
    toggle(app)
    type_key(app, Key.backspace)
    toggle(app)  # stop -> pending
    toggle(app)  # start a new session before answering
    assert app.recording
    assert app.pending_save is not None
    app.resolve_pending_save(True)
    assert len(storage.load_sessions()) == 1
    assert app.recording  # resolving didn't disturb the live session
