"""Counter core: in-memory tallies and derived session stats. Pure logic, no I/O."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping


class Category(Enum):
    """What a key event was reduced to. Key identity is discarded at classification."""

    BACKSPACE = "backspace"
    CTRL_BACKSPACE = "ctrl_backspace"
    DELETE = "delete"
    CTRL_DELETE = "ctrl_delete"
    CTRL_Z = "ctrl_z"
    OVERTYPE = "overtype"  # printable/Enter typed over a keyboard selection (v2.5)
    CUT = "cut"  # Ctrl+X; may be a move, not a deletion - kept distinct (v2.5)
    OTHER = "other"


CORRECTION_CATEGORIES = frozenset(
    {
        Category.BACKSPACE,
        Category.CTRL_BACKSPACE,
        Category.DELETE,
        Category.CTRL_DELETE,
        Category.CTRL_Z,
        Category.OVERTYPE,
        Category.CUT,
    }
)

# Per-app bucket for events whose source app could not be identified.
UNKNOWN_APP = "unknown"


@dataclass(frozen=True)
class SessionStats:
    counts: dict[Category, int]
    total_keystrokes: int
    correction_count: int
    duration_seconds: float
    corrections_per_minute: float
    correction_ratio: float
    app_counts: dict[str, dict[Category, int]] = field(default_factory=dict)


def compute_stats(
    counts: Mapping[Category, int],
    duration_seconds: float,
    app_counts: Mapping[str, Mapping[Category, int]] | None = None,
) -> SessionStats:
    """Derive a SessionStats from raw tallies (live counter or loaded storage row)."""
    full_counts = {cat: counts.get(cat, 0) for cat in Category}
    total = sum(full_counts.values())
    corrections = sum(full_counts[cat] for cat in CORRECTION_CATEGORIES)
    rate = corrections / (duration_seconds / 60) if duration_seconds > 0 else 0.0
    ratio = corrections / total if total > 0 else 0.0
    return SessionStats(
        counts=full_counts,
        total_keystrokes=total,
        correction_count=corrections,
        duration_seconds=duration_seconds,
        corrections_per_minute=rate,
        correction_ratio=ratio,
        app_counts={app: dict(per_app) for app, per_app in (app_counts or {}).items()},
    )


class Counter:
    """Tallies key-event categories for one recording session.

    The clock is injectable so stats math is testable with known timestamps.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._counts: dict[Category, int] = {cat: 0 for cat in Category}
        self._app_counts: dict[str, dict[Category, int]] = {}
        self._start_time: float | None = None
        self._end_time: float | None = None

    def start(self) -> None:
        self._start_time = self._clock()
        self._end_time = None

    def record(self, category: Category, app: str | None = None) -> None:
        self._counts[category] += 1
        per_app = self._app_counts.setdefault(app or UNKNOWN_APP, {cat: 0 for cat in Category})
        per_app[category] += 1

    def stop(self) -> SessionStats:
        self._end_time = self._clock()
        return self.stats()

    def stats(self) -> SessionStats:
        """Current stats: live while recording, final after stop()."""
        if self._start_time is None:
            duration = 0.0
        else:
            end = self._end_time if self._end_time is not None else self._clock()
            duration = end - self._start_time
        return compute_stats(self._counts, duration, self._app_counts)
