"""Reporter: live status line, session summary, history views. Pure formatting."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .counter import CORRECTION_CATEGORIES, Category, SessionStats

if TYPE_CHECKING:
    from .storage import SessionRecord

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
    Category.OVERTYPE: "Overtype (replace)",
    Category.CUT: "Ctrl+X (cut)",
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


NO_SESSIONS_HINT = "no sessions yet - run the tracker and toggle a session with Ctrl+Alt+B"


def render_list(records: list[SessionRecord]) -> str:
    """Bare list of stored sessions: date-time and duration only."""
    if not records:
        return NO_SESSIONS_HINT
    lines = ["=== Stored sessions ==="]
    for r in records:
        lines.append(f"  {r.started_at.replace('T', ' ')}  ({format_duration(r.stats.duration_seconds)})")
    lines.append(f"  {len(records)} session{'s' if len(records) != 1 else ''}")
    return "\n".join(lines)


def render_history(records: list[SessionRecord]) -> str:
    """One line per saved session, identified by its start date and time."""
    if not records:
        return NO_SESSIONS_HINT
    lines = ["=== Session history ==="]
    for r in records:
        s = r.stats
        started = r.started_at.replace("T", " ")
        lines.append(
            f"  {started}  {format_duration(s.duration_seconds):>9}  "
            f"corr {s.correction_count:>6,}  total {s.total_keystrokes:>7,}  "
            f"{s.corrections_per_minute:>6.1f}/min  {s.correction_ratio:>6.1%}"
        )
    return "\n".join(lines)


def render_apps(records: list[SessionRecord]) -> str:
    """Per-app correction totals aggregated across all saved sessions."""
    totals: dict[str, dict[Category, int]] = {}
    for r in records:
        for app, per_app in r.stats.app_counts.items():
            bucket = totals.setdefault(app, {cat: 0 for cat in Category})
            for cat, count in per_app.items():
                bucket[cat] += count
    if not totals:
        return NO_SESSIONS_HINT

    lines = ["=== Corrections by app ==="]
    width = max(len(app) for app in totals)
    by_corrections = sorted(
        totals.items(),
        key=lambda item: sum(item[1][cat] for cat in CORRECTION_CATEGORIES),
        reverse=True,
    )
    for app, counts in by_corrections:
        corrections = sum(counts[cat] for cat in CORRECTION_CATEGORIES)
        total = sum(counts.values())
        ratio = corrections / total if total else 0.0
        lines.append(
            f"  {app:<{width}}  corr {corrections:>6,}  total {total:>7,}  {ratio:>6.1%}"
        )
    return "\n".join(lines)


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
