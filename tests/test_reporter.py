"""Step 5 test cases from PLANNING.md: reporter formatting."""

import pytest

from backspace_tracker.counter import Category, Counter
from backspace_tracker.reporter import format_duration, format_status_line, format_summary


def make_stats(records=(), duration=60.0):
    clock_values = iter([0.0, duration])
    counter = Counter(clock=lambda: next(clock_values))
    counter.start()
    for category in records:
        counter.record(category)
    return counter.stop()


def test_status_line_contains_all_correction_tallies_total_and_rate():
    stats = make_stats(
        [Category.BACKSPACE] * 3 + [Category.CTRL_Z] + [Category.OTHER] * 6,
        duration=120.0,
    )
    line = format_status_line(stats)
    assert "BS 3" in line
    assert "UNDO 1" in line
    assert "C-BS 0" in line
    assert "DEL 0" in line
    assert "C-DEL 0" in line
    assert "total 10" in line
    assert "2.0/min" in line


def test_summary_includes_every_category_duration_rate_and_ratio():
    stats = make_stats(
        [Category.BACKSPACE, Category.OTHER, Category.OTHER, Category.OTHER],
        duration=61.0,
    )
    summary = format_summary(stats)
    assert "Backspace" in summary
    assert "Ctrl+Backspace (word)" in summary
    assert "Delete" in summary
    assert "Ctrl+Delete (word)" in summary
    assert "Ctrl+Z (undo)" in summary
    assert "Other keys" in summary
    assert "Total keystrokes" in summary
    assert "1m 01s" in summary
    assert "Corrections/minute" in summary
    assert "Correction ratio" in summary
    assert "25.0%" in summary


def test_summary_includes_overtype_and_cut():
    stats = make_stats([Category.OVERTYPE, Category.OVERTYPE, Category.CUT], duration=60.0)
    summary = format_summary(stats)
    assert "Overtype (replace)" in summary
    assert "Ctrl+X (cut)" in summary


def test_status_line_omits_overtype_and_cut():
    # Decision: keep the live line compact; overtype/cut are summary-only.
    stats = make_stats([Category.OVERTYPE, Category.CUT], duration=60.0)
    line = format_status_line(stats)
    assert "Overtype" not in line
    assert "cut" not in line.lower()


def test_overtype_and_cut_count_toward_correction_ratio():
    # 2 corrections (overtype + cut) out of 4 total -> 50%.
    stats = make_stats(
        [Category.OVERTYPE, Category.CUT, Category.OTHER, Category.OTHER], duration=60.0
    )
    assert "50.0%" in format_summary(stats)


def test_zero_activity_session_renders_sane_output():
    stats = make_stats([], duration=0.0)
    summary = format_summary(stats)
    assert "0.0" in summary  # corrections/minute
    assert "0.0%" in summary  # correction ratio
    line = format_status_line(stats)
    assert "total 0" in line


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0s"),
        (45, "45s"),
        (61, "1m 01s"),
        (600, "10m 00s"),
        (3723, "1h 02m 03s"),
    ],
)
def test_duration_formatting(seconds, expected):
    assert format_duration(seconds) == expected


def test_thousands_separator_in_summary():
    stats = make_stats([Category.OTHER] * 1203, duration=60.0)
    assert "1,203" in format_summary(stats)
