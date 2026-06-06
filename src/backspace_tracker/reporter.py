"""Reporter: live status line and end-of-session summary. Pure formatting, no state."""

from __future__ import annotations

from .counter import Category, SessionStats

# ASCII labels: classic Windows consoles (cp1252) can't print glyphs like U+232B.
_LABELS = {
    Category.BACKSPACE: "BS",
    Category.CTRL_BACKSPACE: "C-BS",
    Category.DELETE: "DEL",
    Category.CTRL_DELETE: "C-DEL",
    Category.CTRL_Z: "UNDO",
}

_SUMMARY_NAMES = {
    Category.BACKSPACE: "Backspace",
    Category.CTRL_BACKSPACE: "Ctrl+Backspace (word)",
    Category.DELETE: "Delete",
    Category.CTRL_DELETE: "Ctrl+Delete (word)",
    Category.CTRL_Z: "Ctrl+Z (undo)",
    Category.OTHER: "Other keys",
}


def format_duration(seconds: float) -> str:
    """61 -> '1m 01s'; 45 -> '45s'; 3723 -> '1h 02m 03s'."""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def format_status_line(stats: SessionStats) -> str:
    """One-line live view, updated in place while recording."""
    parts = [f"{label} {stats.counts[cat]}" for cat, label in _LABELS.items()]
    parts.append(f"total {stats.total_keystrokes:,}")
    parts.append(f"{stats.corrections_per_minute:.1f}/min")
    return " | ".join(parts)


def format_summary(stats: SessionStats) -> str:
    """Full session summary printed when recording stops."""
    width = max(len(name) for name in _SUMMARY_NAMES.values())
    lines = ["", "=== Session summary ===" ]
    for cat, name in _SUMMARY_NAMES.items():
        lines.append(f"  {name:<{width}}  {stats.counts[cat]:>7,}")
    lines.append(f"  {'Total keystrokes':<{width}}  {stats.total_keystrokes:>7,}")
    lines.append("")
    lines.append(f"  Duration            {format_duration(stats.duration_seconds)}")
    lines.append(f"  Corrections/minute  {stats.corrections_per_minute:.1f}")
    lines.append(f"  Correction ratio    {stats.correction_ratio:.1%}")
    return "\n".join(lines)
