"""Step 4 test cases from PLANNING.md: live wiring (mocked callbacks)."""

import io
import itertools

import pytest
from pynput import keyboard

from backspace_tracker.app import App

Key = keyboard.Key
KeyCode = keyboard.KeyCode


@pytest.fixture
def out():
    return io.StringIO()


@pytest.fixture
def app(out):
    return App(out=out, clock=itertools.count(0.0, 1.0).__next__)


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
