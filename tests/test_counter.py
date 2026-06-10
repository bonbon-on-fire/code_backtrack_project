"""Step 2 test cases from PLANNING.md: Counter core."""

import pytest

from code_backtrack.counter import (
    CORRECTION_CATEGORIES,
    UNKNOWN_APP,
    Category,
    Counter,
)


class FakeClock:
    """Deterministic clock: returns queued times, advancing on each call."""

    def __init__(self, *times: float) -> None:
        self._times = list(times)

    def __call__(self) -> float:
        return self._times.pop(0)


def test_fresh_counter_all_zero_no_crash():
    counter = Counter()
    stats = counter.stats()
    assert all(count == 0 for count in stats.counts.values())
    assert stats.total_keystrokes == 0
    assert stats.correction_count == 0
    assert stats.corrections_per_minute == 0.0
    assert stats.correction_ratio == 0.0


@pytest.mark.parametrize("category", list(Category))
@pytest.mark.parametrize("n", [1, 7])
def test_recording_n_events_tallies_exactly_n(category, n):
    counter = Counter()
    for _ in range(n):
        counter.record(category)
    assert counter.stats().counts[category] == n


def test_correction_ratio_includes_corrections_in_total():
    counter = Counter()
    # 3 corrections + 7 other = 10 total -> ratio 0.3
    for _ in range(3):
        counter.record(Category.BACKSPACE)
    for _ in range(7):
        counter.record(Category.OTHER)
    stats = counter.stats()
    assert stats.total_keystrokes == 10
    assert stats.correction_count == 3
    assert stats.correction_ratio == pytest.approx(0.3)


def test_corrections_per_minute_from_known_timestamps():
    # start at t=0, stop at t=120s, 6 corrections -> 3.0/min
    counter = Counter(clock=FakeClock(0.0, 120.0))
    counter.start()
    for _ in range(6):
        counter.record(Category.BACKSPACE)
    stats = counter.stop()
    assert stats.duration_seconds == pytest.approx(120.0)
    assert stats.corrections_per_minute == pytest.approx(3.0)


def test_zero_duration_session_rate_is_zero_not_crash():
    counter = Counter(clock=FakeClock(5.0, 5.0))
    counter.start()
    counter.record(Category.BACKSPACE)
    stats = counter.stop()
    assert stats.duration_seconds == 0.0
    assert stats.corrections_per_minute == 0.0


def test_ctrl_z_is_a_correction_category():
    # Decision in PLANNING.md: Ctrl+Z counted as its own correction category.
    assert Category.CTRL_Z in CORRECTION_CATEGORIES


def test_other_is_not_a_correction():
    assert Category.OTHER not in CORRECTION_CATEGORIES


def test_overtype_and_cut_are_correction_categories():
    # v2.5: select-then-type-over and Ctrl+X both remove text.
    assert Category.OVERTYPE in CORRECTION_CATEGORIES
    assert Category.CUT in CORRECTION_CATEGORIES


# --- Step 2 (v2) test cases from PLANNING.md: per-app tallies ---


def test_per_app_counts_sum_to_session_totals():
    counter = Counter()
    counter.record(Category.BACKSPACE, app="Code.exe")
    counter.record(Category.BACKSPACE, app="notepad.exe")
    counter.record(Category.OTHER, app="Code.exe")
    counter.record(Category.CTRL_Z, app="chrome.exe")
    stats = counter.stats()

    for cat in Category:
        summed = sum(per_app[cat] for per_app in stats.app_counts.values())
        assert summed == stats.counts[cat]
    assert sum(sum(p.values()) for p in stats.app_counts.values()) == stats.total_keystrokes


def test_app_none_lands_in_unknown():
    counter = Counter()
    counter.record(Category.BACKSPACE)  # no app given
    counter.record(Category.BACKSPACE, app=None)
    stats = counter.stats()
    assert stats.app_counts[UNKNOWN_APP][Category.BACKSPACE] == 2


def test_apps_tracked_separately():
    counter = Counter()
    counter.record(Category.BACKSPACE, app="Code.exe")
    counter.record(Category.DELETE, app="notepad.exe")
    stats = counter.stats()
    assert stats.app_counts["Code.exe"][Category.BACKSPACE] == 1
    assert stats.app_counts["Code.exe"][Category.DELETE] == 0
    assert stats.app_counts["notepad.exe"][Category.DELETE] == 1
