"""Foreground-app probe: process name of the active window, via ctypes only.

Returns a process name like 'Code.exe' - never a window title, which could
leak document/file names. Any failure degrades to UNKNOWN_APP, never an
exception: this runs inside the listener callback for every counted key.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import PureWindowsPath

from .counter import UNKNOWN_APP

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_MAX_PATH = 32767  # long-path aware

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def _query_foreground_process_path() -> str:
    """Full image path of the foreground window's process, or '' on failure."""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(_MAX_PATH)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value
    finally:
        _kernel32.CloseHandle(handle)


def foreground_app() -> str:
    """Process name of the focused window ('Code.exe'), or UNKNOWN_APP."""
    try:
        path = _query_foreground_process_path()
    except Exception:
        return UNKNOWN_APP
    if not path:
        return UNKNOWN_APP
    return PureWindowsPath(path).name or UNKNOWN_APP
