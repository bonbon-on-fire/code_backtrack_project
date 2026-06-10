# Backspace Tracker — Planning

## Overview
A lightweight Windows app that counts correction keystrokes (Backspace, Delete, etc.)
from the moment it's started to the moment it's stopped. Purpose: measure how often
corrections happen while coding, and over time, whether that rate changes.

## Goals
- [x] Count correction keys globally while the app is running
- [x] Global hotkey (Ctrl+Alt+B) toggles recording on/off — minimal usage friction
- [x] Show a session summary (counts, duration, corrections/minute)
- [x] Compute correction ratio (correction keys ÷ total keystrokes)
- [x] Persist session history to spot trends over time
- [x] Per-app breakdown (e.g., VS Code vs terminal vs browser)

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
| Overtype | printable key while a keyboard-made selection is active (v2.5) |
| Ctrl+X | cut — may be deletion or move; own category (v2.5) |
| (all other keys) | counted only toward total, never identified |

## Milestones
| # | Milestone | Status |
|---|-----------|--------|
| 1 | **v1 — Counter**: console app, global hotkey (Ctrl+Alt+B) starts/stops a session, count correction keys + total keystrokes, summary on stop | ☑ |
| 2 | **v2 — Insight**: SQLite session history, correction ratio, per-app filtering/breakdown (active-window process name) | ☑ |
| 3 | **v3 — Daily driver**: tray icon with live count, trend charts, burst detection (N+ backspaces in a row = rewrite vs typo) | ☐ |

## v1 Build Order
- [x] **1. Scaffolding** — `pyproject.toml` (Python 3.12+, pynput), package layout under
  `src/code_backtrack/`, `.gitignore`, README stub
  - Test: `pip install -e .` succeeds; `python -c "import code_backtrack"` works
  - Test: `python -m code_backtrack` starts without error (and exits cleanly)
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
  - Test: Ctrl+Alt+B → toggle signal, **never counted** in any category
  - Test: Ctrl+Shift+Backspace → `CTRL_BACKSPACE` (shift doesn't change backspace in editors)
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
- [x] **6. End-to-end smoke test** (manual) — verify the real hook against known input
  (passed 2026-06-06: repeats counted during hold, C-BS/UNDO in own categories,
  summary matched live tallies, second session started from zero)
  - Type 10 Backspaces in another app → summary shows exactly 10
  - Hold Backspace ~2s → count visibly exceeds 10 (repeats counted)
  - Press Ctrl+Backspace, Ctrl+Z → each lands in its own category
  - Type while idle (before first toggle / after stop) → nothing counted
  - Toggle across two sessions → second session starts from zero

## v2 Build Order
- [x] **1. Storage layer** (`storage.py`) — stdlib `sqlite3`; schema:
  `sessions(id, started_at, duration_seconds, <per-category counts>)` and
  `app_counts(session_id, app, <per-category counts>)`; DB at
  `%LOCALAPPDATA%\code-backtrack\sessions.db`
  - Test: save→load round-trip preserves every count
  - Test: schema auto-created on a fresh DB
  - Test: multiple sessions ordered by start time
  - Test: app rows linked to the right session
- [x] **2. Per-app tallies** (`counter.py`) — `record(category, app=None)`;
  `SessionStats` gains `app_counts`
  - Test: per-app counts sum to the session totals
  - Test: `app=None` lands in `"unknown"`
  - Test: all v1 counter tests still pass (regression guard)
- [x] **3. Active-window probe** (`activewindow.py`) — ctypes
  (`GetForegroundWindow` → `QueryFullProcessImageName`), process name only
  - Test: returns a non-empty string on a real desktop
  - Test: failure paths (mocked) → `"unknown"`, never a crash
- [x] **4. Wire-up** (`app.py`) — probe foreground app per counted event; persist
  session to SQLite on stop; print `saved session #N`
  - Test: stats flow into storage on stop (fake probe, no real hook)
  - Test: probe failure still counts the key (under `"unknown"`)
- [x] **5. History CLI** (`__main__.py` + reporter) — `history` lists recent sessions
  (date, duration, corrections/min, ratio); `apps` shows per-app breakdown
  - Test: output includes saved sessions with v1 reporter formatting
  - Test: empty DB → friendly "no sessions yet"
  - Test: bare `python -m code_backtrack` still runs the tracker (unchanged)
- [x] **6. End-to-end smoke test** (manual) — one session typing in two different
  apps; `history` shows it; `apps` splits counts between the two processes;
  a second session appends, doesn't overwrite
  (passed 2026-06-06: firefox.exe vs Notepad.exe split cleanly, ambient
  explorer/terminal keys attributed, sessions #2-#4 appended)

## v2.5 Build Order — selection edge cases
Select-then-type-over deletes text with no Backspace/Delete event, so corrections
are undercounted. Fix with a keyboard-only selection heuristic (no text access,
no mouse hook — see Known Limits).
- [x] **1. Selection state machine** (`listener.py`) — "selection probably active"
  flag: set by Shift+Arrow/Home/End/PgUp/PgDn and Ctrl+A; survives Ctrl+C (copy);
  cleared by plain arrows, Escape, Backspace/Delete, and after one OVERTYPE.
  OVERTYPE triggers on printable keys + Enter (Tab stays OTHER — usually indent).
  - Test: Shift+Right then letter → `OVERTYPE`
  - Test: Ctrl+A then letter → `OVERTYPE`
  - Test: Shift+Right, plain Right (collapse), letter → `OTHER`, no overtype
  - Test: Shift+Right, Escape, letter → `OTHER`
  - Test: Shift+Right, Ctrl+C, letter → `OVERTYPE` (copy keeps selection)
  - Test: flag clears after one overtype — next letter is `OTHER`
  - Test: selection + Ctrl+V (paste-over) → `OVERTYPE`
  - Test: selection + Delete still counts as `DELETE`, not double-counted
- [x] **2. New categories** (`counter.py` + `storage.py`) — `OVERTYPE` and `CUT`
  (Ctrl+X) as correction categories; schema gains the two columns (old DBs
  backfilled via `ALTER TABLE ... DEFAULT 0` on open)
  - Test: both are in `CORRECTION_CATEGORIES`
  - Test: Ctrl+X → `CUT`; Ctrl+Shift+X → `OTHER`
  - Test: held Ctrl+Z (key-repeat) → one `CTRL_Z` per repeat event, same
    policy as held Backspace
  - Test: old DBs still load (column migration or default 0)
- [x] **3. Reporter** — OVERTYPE/CUT in the summary only (live status line kept
  compact, by decision)
- [ ] **4. Scripted verification session** (manual) — ~15 editing behaviors
  (select-replace, cut-paste, undo chains, autocomplete accept, multi-cursor)
  performed in a real editor; diff expected vs actual counts; record results here

## Known Limits (accepted blind spots)
The hook sees keystrokes, not text or selection state. Reading actual text would
require accessibility APIs — keylogger territory, against the privacy principle.
Invisible and accepted:
- Mouse selections (drag, double-click) then type-over — a mouse hook can't tell
  "select then replace" from "place cursor then type"; too many false positives
- Menu-driven undo/delete, multi-cursor magnitude (1 backspace = N deletions),
  vim-mode commands (dd, ciw), autocomplete/refactors replacing typed text
- Ctrl+X ambiguity: cut may be a move, not a deletion — counted as its own
  category so the data can decide later

## Decisions
- **Hotkey**: Ctrl+Alt+B toggles recording. The app launches idle; the hotkey starts a
  session, pressing it again stops and prints the summary. The hotkey press itself is
  never counted. (Originally Ctrl+Shift+Backspace — abandoned because the hook only
  observes keys, and that combo passes through to the focused app as a word-delete.
  Lesson: a hotkey must be a no-op in apps, not just unbound as a shortcut.)
- **Ctrl+Z**: counted as its own category (cheap to add; data can't be retrofitted).
- **v2 dependencies**: none added — ctypes for the window probe (no psutil).
- **v2 DB location**: `%LOCALAPPDATA%\code-backtrack\sessions.db` — survives repo
  moves; not in the project dir.
- **v2 app identity**: process name only (window titles leak document/file names,
  violating the privacy principle). Probe failure → key counted under `"unknown"`,
  so totals stay accurate and only the breakdown degrades.
- **Saving is opt-in per session**: on stop, the terminal asks `save this session?
  [Y/n]` (Enter = save; Ctrl+C during the prompt also saves — losing data is the
  worse failure). Prompt runs on the main loop; the hotkey thread can't block.
- **Sessions are identified by start date-time** (`2026-06-06 13:27:45`), not by
  numeric id. The integer id remains internal to SQLite as a join key.
- **Key-repeat**: every repeat counts — each repeat deletes a real character, so it's
  genuine correction volume. No thresholding in v1.
- **v2.5 overtype trigger**: printable characters + Enter replace a live selection
  (counted OVERTYPE). Tab stays OTHER — Tab over a selection is usually indent, and
  the false-positive risk isn't worth the rare catch.
- **v2.5 reporter**: OVERTYPE/CUT appear in the session summary only; the live status
  line stays compact with the original five categories.

## Open Questions
- Burst threshold (v3): how many consecutive backspaces counts as a "rewrite"?
  Starting guess: ≥10 — tune once v2 session data exists.

## Notes
- v1 counts everywhere; the user controls data quality by only running it while coding.
  Per-app filtering arrives in v2.
- Privacy principle: no key identities or sequences are ever written to disk — only
  category counts and timestamps.
