"""Step 3 (v2) test cases from PLANNING.md: active-window probe."""

from code_backtrack import activewindow
from code_backtrack.activewindow import foreground_app
from code_backtrack.counter import UNKNOWN_APP


def test_returns_nonempty_string_on_real_desktop():
    # Real probe: either an actual process name or the UNKNOWN_APP fallback
    # (e.g. no foreground window on a locked/headless desktop) - never empty.
    name = foreground_app()
    assert isinstance(name, str)
    assert name


def test_query_failure_returns_unknown(monkeypatch):
    monkeypatch.setattr(activewindow, "_query_foreground_process_path", lambda: "")
    assert foreground_app() == UNKNOWN_APP


def test_query_exception_returns_unknown(monkeypatch):
    def boom():
        raise OSError("hook denied")

    monkeypatch.setattr(activewindow, "_query_foreground_process_path", boom)
    assert foreground_app() == UNKNOWN_APP


def test_path_reduced_to_process_name(monkeypatch):
    monkeypatch.setattr(
        activewindow,
        "_query_foreground_process_path",
        lambda: r"C:\Users\someone\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    )
    assert foreground_app() == "Code.exe"
