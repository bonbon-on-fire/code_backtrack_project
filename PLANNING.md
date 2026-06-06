# Backspace Tracker — Planning

## Overview
A lightweight Windows app that counts correction keystrokes (Backspace, Delete, etc.)
from the moment it's started to the moment it's stopped. Purpose: measure how often
corrections happen while coding, and over time, whether that rate changes.

## Goals
- [ ] Count correction keys globally while the app is running
- [ ] Global hotkey (Ctrl+Shift+Backspace) toggles recording on/off — minimal usage friction
- [ ] Show a session summary (counts, duration, corrections/minute)
- [ ] Compute correction ratio (correction keys ÷ total keystrokes)
- [ ] Persist session history to spot trends over time
- [ ] Per-app breakdown (e.g., VS Code vs terminal vs browser)

## Non-Goals
- Logging *which* keys are pressed or reconstructing typed text — this is a
  **counter, not a keylogger**. Only aggregate numbers are ever stored.
- Cross-platform support (Windows-only for now)
- Cloud sync / accounts

## Tech Stack
- **Python 3.12+**
- **pynput** — global keyboard hook
- **SQLite** (stdlib `sqlite3`) — session persistence (v2)
- Console app for v1; tray app (e.g., `pystray`) considered for v3

## Architecture
```
┌─────────────┐    key events    ┌──────────────┐    aggregates    ┌─────────────┐
│ pynput hook │ ───────────────► │ Counter core │ ───────────────► │ Reporter    │
│ (listener)  │                  │ (in-memory   │                  │ (console /  │
└─────────────┘                  │  tallies)    │                  │  summary)   │
                                 └──────┬───────┘                  └─────────────┘
                                        │ on exit / interval
                                        ▼
                                 ┌──────────────┐
                                 │ SQLite store │  (v2)
                                 └──────────────┘
```
- **Listener**: subscribes to global key events; immediately reduces each event to a
  category (backspace / ctrl+backspace / delete / ctrl+delete / other) and discards it.
- **Counter core**: in-memory tallies per category + total keystrokes + timestamps.
- **Reporter**: live console line while running; full summary on Ctrl+C.

### Keys tracked
| Key | Meaning |
|-----|---------|
| Backspace | single-char correction |
| Ctrl+Backspace | word-level correction |
| Delete | forward delete |
| Ctrl+Delete | forward word delete |
| Ctrl+Z | undo (heaviest correction) — counted as its own category |
| (all other keys) | counted only toward total, never identified |

## Milestones
| # | Milestone | Status |
|---|-----------|--------|
| 1 | **v1 — Counter**: console app, global hotkey (Ctrl+Shift+Backspace) starts/stops a session, count correction keys + total keystrokes, summary on stop | ☐ |
| 2 | **v2 — Insight**: SQLite session history, correction ratio, per-app filtering/breakdown (active-window process name) | ☐ |
| 3 | **v3 — Daily driver**: tray icon with live count, trend charts, burst detection (N+ backspaces in a row = rewrite vs typo) | ☐ |

## v1 Build Order
- [x] **1. Scaffolding** — `pyproject.toml` (Python 3.12+, pynput), package layout under
  `src/backspace_tracker/`, `.gitignore`, README stub
  - Test: `pip install -e .` succeeds; `python -c "import backspace_tracker"` works
  - Test: `python -m backspace_tracker` starts without error (and exits cleanly)
- [x] **2. Counter core** (`counter.py`) — `Category` enum, `Counter` class with tallies,
  timestamps, derived stats (duration, corrections/min, correction ratio). Pure logic,
  zero I/O, unit tests alongside
  - Test: fresh counter → all tallies zero, ratio/rate are 0 (no ZeroDivisionError)
  - Test: recording N events per category → each tally exactly N
  - Test: correction ratio = correction keys ÷ total keystrokes (corrections included
    in the total)
  - Test: corrections/minute computed from session duration (known timestamps in,
    known rate out)
  - Test: zero-duration session → rate is 0, not a crash
- [x] **3. Event classification** (`listener.py`, logic half) — (key, modifier state) →
  `Category` mapping, modifier tracking. Tested with synthetic events
  - Test: Backspace → `BACKSPACE`; Delete → `DELETE`; letter/other key → `OTHER`
  - Test: Ctrl+Backspace → `CTRL_BACKSPACE`; Ctrl+Delete → `CTRL_DELETE`;
    Ctrl+Z → `CTRL_Z`
  - Test: Ctrl+**Shift**+Backspace → toggle signal, **never counted** in any category
  - Test: Ctrl+Shift+Z (redo) → `OTHER`, not `CTRL_Z`
  - Test: left and right Ctrl both register as Ctrl held
  - Test: modifier release tracked — Backspace *after* Ctrl released → `BACKSPACE`,
    not `CTRL_BACKSPACE`
  - Test: repeated Backspace events (key held) → one count per event
- [x] **4. Live wiring** — real `pynput.Listener`, hotkey toggles idle ↔ recording,
  Ctrl+C clean exit
  - Test (mocked callbacks): events while **idle** count nothing
  - Test (mocked callbacks): hotkey → recording starts; hotkey again → session stops
    and stats are finalized
  - Test (mocked callbacks): hotkey press itself adds nothing to the new session's
    counts
  - Test: Ctrl+C while recording → session finalized, listener stopped, clean exit
- [x] **5. Reporter** (`reporter.py`) — live in-place status line while recording,
  summary table on session stop
  - Test: status line contains all correction tallies, total, and rate
  - Test: summary includes every category, duration, corrections/min, correction ratio
  - Test: zero-activity session renders sane output (0s and 0%, no crash)
  - Test: duration formatting (e.g., 61s → `1m 01s`)
- [ ] **6. End-to-end smoke test** (manual) — verify the real hook against known input
  - Type 10 Backspaces in another app → summary shows exactly 10
  - Hold Backspace ~2s → count visibly exceeds 10 (repeats counted)
  - Press Ctrl+Backspace, Ctrl+Z → each lands in its own category
  - Type while idle (before first toggle / after stop) → nothing counted
  - Toggle across two sessions → second session starts from zero

## Decisions
- **Hotkey**: Ctrl+Shift+Backspace toggles recording. The app launches idle; the hotkey
  starts a session, pressing it again stops and prints the summary. The hotkey press
  itself is never counted (Shift check happens before Ctrl+Backspace classification).
- **Ctrl+Z**: counted as its own category (cheap to add; data can't be retrofitted).
- **Key-repeat**: every repeat counts — each repeat deletes a real character, so it's
  genuine correction volume. No thresholding in v1.

## Open Questions
- Burst threshold (v3): how many consecutive backspaces counts as a "rewrite"?
  Starting guess: ≥10 — tune once v2 session data exists.

## Notes
- v1 counts everywhere; the user controls data quality by only running it while coding.
  Per-app filtering arrives in v2.
- Privacy principle: no key identities or sequences are ever written to disk — only
  category counts and timestamps.
