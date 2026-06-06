"""App loop: wires the classifier, counter, and reporter to the global hook.

States: IDLE (counting nothing) <-> RECORDING (hotkey toggles). Ctrl+C quits,
finalizing any in-flight session first.
"""

from __future__ import annotations

import sys
import time
from typing import Callable, TextIO

from pynput import keyboard

from .counter import Category, Counter, SessionStats
from .listener import EventClassifier, Signal
from .reporter import format_status_line, format_summary

HOTKEY_HINT = "Ctrl+Shift+Backspace"


class App:
    """Idle <-> recording state machine. Pure logic; the pynput hook calls into it."""

    def __init__(
        self,
        out: TextIO = sys.stdout,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._out = out
        self._clock = clock
        self._classifier = EventClassifier()
        self._counter: Counter | None = None
        self.last_stats: SessionStats | None = None

    @property
    def recording(self) -> bool:
        return self._counter is not None

    def on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        result = self._classifier.on_press(key)
        if result is Signal.TOGGLE:
            self._toggle()
        elif isinstance(result, Category) and self._counter is not None:
            self._counter.record(result)
            self._show_status()

    def on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        self._classifier.on_release(key)

    def shutdown(self) -> None:
        """Ctrl+C: finalize an in-flight session before exiting."""
        if self._counter is not None:
            self._stop_session()
        self._out.write("bye\n")
        self._out.flush()

    def _toggle(self) -> None:
        if self._counter is None:
            self._counter = Counter(clock=self._clock)
            self._counter.start()
            self._out.write(f"\nrecording - {HOTKEY_HINT} to stop\n")
            self._out.flush()
        else:
            self._stop_session()

    def _stop_session(self) -> None:
        assert self._counter is not None
        self.last_stats = self._counter.stop()
        self._counter = None
        self._out.write("\n" + format_summary(self.last_stats) + "\n")
        self._out.write(f"\nidle - {HOTKEY_HINT} to start a new session\n")
        self._out.flush()

    def _show_status(self) -> None:
        assert self._counter is not None
        line = format_status_line(self._counter.stats())
        # \r + pad: overwrite the previous status line in place.
        self._out.write(f"\r{line:<79}")
        self._out.flush()


def run() -> None:
    app = App()
    listener = keyboard.Listener(on_press=app.on_press, on_release=app.on_release)
    listener.start()
    print(f"backspace-tracker: idle - press {HOTKEY_HINT} to start recording (Ctrl+C quits)")
    try:
        while listener.running:
            time.sleep(0.2)  # sleep-poll so Ctrl+C is delivered promptly on Windows
    except KeyboardInterrupt:
        app.shutdown()
    finally:
        listener.stop()
