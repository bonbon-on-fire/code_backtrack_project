"""Event classification: reduce key events to categories, then discard them.

This is the privacy boundary - key identity never leaves this module. Only the
resulting Category (or the toggle signal) is passed on.
"""

from __future__ import annotations

from enum import Enum, auto

from pynput import keyboard

from .counter import Category

_CTRL_KEYS = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}
_SHIFT_KEYS = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}
_ALT_KEYS = {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr}
_VK_Z = 0x5A  # virtual-key code for Z; with Ctrl held, char arrives as '\x1a'
_VK_B = 0x42  # virtual-key code for B; with Ctrl held, char arrives as '\x02'


class Signal(Enum):
    """Non-category classification results."""

    TOGGLE = auto()  # Ctrl+Alt+B: start/stop recording, never counted


def _is_z(key: keyboard.Key | keyboard.KeyCode) -> bool:
    if getattr(key, "vk", None) == _VK_Z:
        return True
    return getattr(key, "char", None) in ("z", "Z", "\x1a")


def _is_b(key: keyboard.Key | keyboard.KeyCode) -> bool:
    if getattr(key, "vk", None) == _VK_B:
        return True
    return getattr(key, "char", None) in ("b", "B", "\x02")


class EventClassifier:
    """Tracks modifier state and reduces each key press to a Category or Signal.

    Modifier keys themselves (Ctrl/Shift/...) return None: they are chord
    components, not keystrokes.
    """

    def __init__(self) -> None:
        self._ctrl_down: set[keyboard.Key] = set()
        self._shift_down: set[keyboard.Key] = set()
        self._alt_down: set[keyboard.Key] = set()

    def on_press(self, key: keyboard.Key | keyboard.KeyCode) -> Category | Signal | None:
        if key in _CTRL_KEYS:
            self._ctrl_down.add(key)
            return None
        if key in _SHIFT_KEYS:
            self._shift_down.add(key)
            return None
        if key in _ALT_KEYS:
            self._alt_down.add(key)
            return None

        ctrl = bool(self._ctrl_down)
        shift = bool(self._shift_down)
        alt = bool(self._alt_down)

        if ctrl and alt and _is_b(key):
            # The hotkey. Ctrl+Alt+B is a no-op in apps, so it has no side
            # effects in whatever window has focus.
            return Signal.TOGGLE

        if key == keyboard.Key.backspace:
            # Shift+Backspace and Ctrl+Shift+Backspace behave like their
            # unshifted forms in editors, so shift is irrelevant here.
            return Category.CTRL_BACKSPACE if ctrl else Category.BACKSPACE

        if key == keyboard.Key.delete:
            if ctrl and shift:
                # Ctrl+Shift+Delete opens dialogs (e.g. browser clear-history),
                # it does not delete text.
                return Category.OTHER
            return Category.CTRL_DELETE if ctrl else Category.DELETE

        if ctrl and _is_z(key):
            # Ctrl+Shift+Z is redo, not a correction.
            return Category.OTHER if shift else Category.CTRL_Z

        return Category.OTHER

    def on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        self._ctrl_down.discard(key)
        self._shift_down.discard(key)
        self._alt_down.discard(key)
