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


class Signal(Enum):
    """Non-category classification results."""

    TOGGLE = auto()  # Ctrl+Alt+B: start/stop recording, never counted


def _is_letter(key: keyboard.Key | keyboard.KeyCode, letter: str) -> bool:
    """True if `key` is the given ASCII letter, however it arrives.

    A letter can reach us as its KeyCode char, its uppercase form, its
    virtual-key code, or - when Ctrl is held on Windows - the matching control
    char (e.g. Ctrl+Z -> '\\x1a'). All four are folded to the same letter here.
    """
    vk = ord(letter.upper())
    if getattr(key, "vk", None) == vk:
        return True
    char = getattr(key, "char", None)
    return char in (letter, letter.upper(), chr(vk - 0x40))


def _is_printable(key: keyboard.Key | keyboard.KeyCode) -> bool:
    """A single visible character (letter, digit, symbol). Space/Enter/Tab are
    special keys (no .char) and are handled as OTHER."""
    char = getattr(key, "char", None)
    return isinstance(char, str) and len(char) == 1 and char.isprintable()


class EventClassifier:
    """Tracks modifier state and reduces each key press to a Category or Signal.

    Modifier keys themselves (Ctrl/Shift/...) return None: they are chord
    components, not keystrokes.

    A printable content key (letter/digit/symbol) with no Ctrl/Alt held is a
    typed character (CHAR). Backspace/Delete are deletions; word deletes need
    Ctrl. The v2.5 keyboard-selection / OVERTYPE heuristic was retired in v3 -
    it could mis-divert a typed character away from the CHAR count, and the
    OVERTYPE magnitude was never measurable anyway (see PLANNING.md).
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

        if ctrl and alt and _is_letter(key, "b"):
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

        if ctrl and _is_letter(key, "x"):
            # Ctrl+Shift+X is not cut. A real cut removes the selection.
            return Category.OTHER if shift else Category.CUT

        if ctrl and _is_letter(key, "z"):
            # Ctrl+Shift+Z is redo, not a correction.
            return Category.OTHER if shift else Category.CTRL_Z

        if _is_printable(key) and not ctrl and not alt:
            # A typed content character (letter/digit/symbol) = added text (v3).
            # Space/Enter/Tab arrive as special keys (no .char), so they fall
            # through to OTHER - structure, not content, excluded from "added".
            return Category.CHAR

        return Category.OTHER

    def on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        self._ctrl_down.discard(key)
        self._shift_down.discard(key)
        self._alt_down.discard(key)
