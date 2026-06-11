"""System-tray front-end (v4): run the tracker alongside work, no terminal.

Storage-free by decision - sessions are live-only and discarded on stop. The
tracking logic lives in App; this module only adds the tray view and controls.
"""

from __future__ import annotations

import threading
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from .app import App
from .reporter import format_duration, format_tray_tooltip

ICON_SIZE = 64
_MARGIN = 8
_IDLE_COLOR = (130, 130, 130, 255)  # grey dot
_RECORDING_COLOR = (220, 50, 47, 255)  # red dot


def make_icon_image(recording: bool) -> Image.Image:
    """A small circle icon drawn at runtime - grey when idle, red when recording.

    Generated in code so there are no image assets to ship.
    """
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = _RECORDING_COLOR if recording else _IDLE_COLOR
    draw.ellipse([_MARGIN, _MARGIN, ICON_SIZE - _MARGIN, ICON_SIZE - _MARGIN], fill=color)
    return img


class TrayController:
    """Binds an App to a system-tray icon: menu, tooltip, and live refresh.

    The icon object is passed in (never created here) so the logic is testable
    with a fake. Both the Ctrl+Alt+B hotkey and the menu funnel through
    `App.toggle`; a lock keeps the two driving threads from racing. All visible
    state (icon image, tooltip, transition notification) is applied in `refresh`,
    so a hotkey toggle and a menu toggle update the UI the same way.
    """

    def __init__(
        self,
        app: App,
        on_quit: Callable[[], None] | None = None,
        icon_factory: Callable[[bool], Image.Image] = make_icon_image,
    ) -> None:
        self.app = app
        self._on_quit = on_quit
        self._icon_factory = icon_factory
        self._lock = threading.RLock()
        self._last_recording = False

    # --- text helpers (pystray may call text callables with the item) ---

    def toggle_label(self, *_: object) -> str:
        return "Stop recording" if self.app.recording else "Start recording"

    def tooltip(self, *_: object) -> str:
        return format_tray_tooltip(self.app.current_stats(), self.app.recording)

    def summary_notification(self) -> str:
        s = self.app.last_stats
        if s is None:
            return "Session ended"
        return (
            f"typed {s.chars_added:,} | deleted {s.chars_deleted:,} | "
            f"del {s.delete_pct:.0%} | {format_duration(s.duration_seconds)}"
        )

    def build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(self.toggle_label, self.on_toggle),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.tooltip, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.on_quit),
        )

    # --- actions ---

    def on_toggle(self, icon: object = None, item: object = None) -> None:
        with self._lock:
            self.app.toggle()
        self.refresh(icon)

    def on_quit(self, icon: object = None, item: object = None) -> None:
        with self._lock:
            if self.app.recording:
                self.app.toggle()  # finalize (storage-free: discarded)
        if self._on_quit is not None:
            self._on_quit()
        if icon is not None:
            icon.stop()

    def refresh(self, icon: object) -> None:
        """Push current state to the icon: image, tooltip, and - on a
        recording->idle transition - a one-shot summary notification."""
        if icon is None:
            return
        with self._lock:
            recording = self.app.recording
            icon.icon = self._icon_factory(recording)
            icon.title = self.tooltip()
            if self._last_recording and not recording:
                icon.notify(self.summary_notification(), "code-backtrack")
            self._last_recording = recording
        icon.update_menu()
