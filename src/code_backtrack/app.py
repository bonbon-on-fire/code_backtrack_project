"""App loop: wires the classifier, counter, and reporter to the global hook.

States: IDLE (counting nothing) <-> RECORDING (hotkey toggles). Ctrl+C quits,
finalizing any in-flight session first.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from typing import Callable, TextIO

from pynput import keyboard

from .activewindow import foreground_app
from .counter import Category, Counter, SessionStats
from .listener import EventClassifier, Signal
from .reporter import format_status_line, format_summary
from .storage import Storage

HOTKEY_HINT = "Ctrl+Alt+B"


class App:
    """Idle <-> recording state machine. Pure logic; the pynput hook calls into it."""

    def __init__(
        self,
        out: TextIO = sys.stdout,
        clock: Callable[[], float] = time.monotonic,
        probe: Callable[[], str] = foreground_app,
        storage: Storage | None = None,
    ) -> None:
        self._out = out
        self._clock = clock
        self._probe = probe
        self._storage = storage
        self._classifier = EventClassifier()
        self._counter: Counter | None = None
        self._session_started_at: datetime | None = None
        self._pending_save: tuple[datetime, SessionStats] | None = None
        self.last_stats: SessionStats | None = None

    @property
    def pending_save(self) -> tuple[datetime, SessionStats] | None:
        """A finished session awaiting the user's save/discard decision."""
        return self._pending_save

    @property
    def recording(self) -> bool:
        return self._counter is not None

    def current_stats(self) -> SessionStats | None:
        """Live stats while recording, else None. Used by the tray view."""
        return self._counter.stats() if self._counter is not None else None

    def on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        result = self._classifier.on_press(key)
        if result is Signal.TOGGLE:
            self.toggle()
        elif isinstance(result, Category) and self._counter is not None:
            self._counter.record(result, app=self._probe())
            self._show_status()

    def on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        self._classifier.on_release(key)

    def shutdown(self) -> None:
        """Ctrl+C: finalize an in-flight session before exiting."""
        if self._counter is not None:
            self._stop_session()

    def toggle(self) -> None:
        """Start a session if idle, otherwise stop and finalize it. Shared by the
        Ctrl+Alt+B hotkey and the tray menu."""
        if self._counter is None:
            self._counter = Counter(clock=self._clock)
            self._counter.start()
            self._session_started_at = datetime.now()
            self._out.write(f"\nrecording - {HOTKEY_HINT} to stop\n")
            self._out.flush()
        else:
            self._stop_session()

    def _stop_session(self) -> None:
        assert self._counter is not None
        self.last_stats = self._counter.stop()
        self._counter = None
        self._out.write("\n" + format_summary(self.last_stats) + "\n")
        if self._storage is not None and self._session_started_at is not None:
            # Saving waits for the user's answer; the main loop prompts and
            # calls resolve_pending_save (input() can't run on this thread).
            self._pending_save = (self._session_started_at, self.last_stats)
        else:
            self._out.write(f"\nidle - {HOTKEY_HINT} to start a new session\n")
        self._out.flush()

    def resolve_pending_save(self, save: bool) -> None:
        if self._pending_save is None:
            return
        started_at, stats = self._pending_save
        self._pending_save = None
        if save and self._storage is not None:
            self._storage.save_session(started_at, stats)
            self._out.write(f"saved session {started_at:%Y-%m-%d %H:%M:%S}\n")
        else:
            self._out.write("session discarded\n")
        self._out.write(f"\nidle - {HOTKEY_HINT} to start a new session\n")
        self._out.flush()

    def _show_status(self) -> None:
        assert self._counter is not None
        line = format_status_line(self._counter.stats())
        # \r + pad: overwrite the previous status line in place.
        self._out.write(f"\r{line:<79}")
        self._out.flush()


def _prompt_pending_save(app: App) -> None:
    """Main thread only: ask about a finished session, then resolve it."""
    if app.pending_save is None:
        return
    try:
        answer = input("\nsave this session? [Y/n]: ")
    except (EOFError, KeyboardInterrupt):
        answer = ""  # default to saving; losing data is the worse failure
    app.resolve_pending_save(answer.strip().lower() not in ("n", "no"))


def run() -> None:
    app = App(storage=Storage())
    listener = keyboard.Listener(on_press=app.on_press, on_release=app.on_release)
    listener.start()
    print(f"code-backtrack: idle - press {HOTKEY_HINT} to start recording (Ctrl+C quits)")
    try:
        while listener.running:
            time.sleep(0.2)  # sleep-poll so Ctrl+C is delivered promptly on Windows
            _prompt_pending_save(app)
    except KeyboardInterrupt:
        app.shutdown()
        _prompt_pending_save(app)
    finally:
        listener.stop()
    print("bye")
