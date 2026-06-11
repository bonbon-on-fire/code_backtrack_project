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
| Key | Meaning | Chars (v3) |
|-----|---------|------------|
| Printable char (letter/digit/symbol) | a typed character — **added** | +1 added |
| Backspace | single-char correction | −1 deleted |
| Delete | forward delete | −1 deleted |
| Ctrl+Backspace | word-level correction (size unknown) | −5 deleted (estimate) |
| Ctrl+Delete | forward word delete (size unknown) | −5 deleted (estimate) |
| Ctrl+Z | undo (heaviest correction) — own category | not in char totals (no sane estimate) |
| Overtype | **retired in v3** — heuristic removed; enum/column kept for stored history | never produced |
| Ctrl+X | cut — may be deletion or move; own category (v2.5) | not in char totals (selection size unknown) |
| Space / Enter / Tab / nav / function keys | counted only toward total, never identified | not added (by decision) |

In v3 the character model is the headline; the per-key category counts above are
still recorded (cheap, already collected) but become a secondary breakdown.

## Milestones
| # | Milestone | Status |
|---|-----------|--------|
| 1 | **v1 — Counter**: console app, global hotkey (Ctrl+Alt+B) starts/stops a session, count correction keys + total keystrokes, summary on stop | ☑ |
| 2 | **v2 — Insight**: SQLite session history, correction ratio, per-app filtering/breakdown (active-window process name) | ☑ |
| 3 | **v3 — Meaningful metric**: characters added vs. characters deleted, and the delete % — one number that says "how much of what I type do I end up removing" | ☑ |
| 4 | **v4 — Daily driver**: system-tray icon with live count + start/stop menu, so the tracker runs alongside work without a terminal. (Trend charts and burst detection were considered and dropped — not wanted.) | ☐ |

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
- [~] **4. Scripted verification session** (manual) — **won't do, superseded by
  v3.** The v3 character model retired the OVERTYPE selection heuristic this step
  was meant to validate (printable keys now always count as CHAR). The remaining
  v2.5 behaviors (single/word deletes, cut, undo) are covered by unit tests and the
  v3 smoke test, so a dedicated hands-on session adds no value. The checklist in
  `tests/v2.5_manual_verification.md` is kept for reference but its overtype rows
  are obsolete.

## v3 Build Order — meaningful metric (chars added vs deleted)
The pile of per-category counts never resolved into one readable number. v3 adds a
**character model**: how many characters were typed (added) vs. removed (deleted),
and the **delete %** (`deleted ÷ added`). It stays on the counter side of the
privacy line — a single Backspace/Delete is provably one character, and word
deletes use a fixed estimate, so no text or selection is ever read.

- Char accounting:
  - `chars_added` = printable character keys only (letters, digits, symbols).
    **Space, Enter, and Tab do NOT count as added** (by decision — they're
    structure, not content; keeps the ratio about typed text).
  - `chars_deleted` = Backspace + Delete (1 each, repeats included) +
    `(Ctrl+Backspace + Ctrl+Delete) × WORD_DELETE_CHARS`.
  - `WORD_DELETE_CHARS = 5` — average word length. Word deletes are rare in normal
    use and skew long when used, so this slightly under-counts, but the low
    frequency makes the error negligible. Single named constant, easy to tune.
  - Undo / Overtype / Cut are **excluded** from char totals (no defensible size)
    but stay as event counts in the secondary breakdown.
  - `delete_pct = chars_deleted ÷ chars_added` (0 when nothing typed, no crash);
    `net_chars = chars_added − chars_deleted`.

- [x] **1. New `CHAR` category** (`listener.py` + `counter.py`) — a printable
  character key (not consumed as overtype/hotkey) classifies as `Category.CHAR`
  instead of folding into `OTHER`. Space/Enter/Tab stay `OTHER`. Total keystrokes
  and the existing correction ratio are unchanged (CHAR just splits out of OTHER).
  - Test: a letter/digit/symbol → `CHAR`; Space/Enter/Tab → `OTHER`
  - Test: printable key during a live selection still → `OVERTYPE`, not `CHAR`
  - Test: Ctrl/Alt + letter (shortcuts) → not `CHAR`
  - Test: all v2.5 classifier tests still pass (regression guard)
- [x] **2. Char stats** (`counter.py`) — `WORD_DELETE_CHARS` constant; derive
  `chars_added`, `chars_deleted`, `delete_pct`, `net_chars` in `compute_stats`.
  - Test: typed N printable, M backspaces → added=N, deleted=M, pct=M/N
  - Test: each Ctrl+Backspace / Ctrl+Delete adds 5 to deleted
  - Test: Undo/Overtype/Cut do **not** move the char totals
  - Test: zero typed → delete_pct = 0, no ZeroDivisionError
- [x] **3. Storage** (`storage.py`) — persist the `char` count column (added chars);
  deleted/pct/net are derived on read from existing columns, so only one new
  column. Old DBs backfilled via `ALTER TABLE ... DEFAULT 0` (same pattern as v2.5).
  - Test: save→load round-trip preserves the char count
  - Test: old DB without the column still loads (migration / default 0)
- [x] **4. Reporter** (`reporter.py`) — headline block leads with
  `typed / deleted / delete % / net`; the per-category tallies move below as a
  compact breakdown. `history` shows delete % per session.
  - Test: summary shows added, deleted, delete %, net
  - Test: zero-activity session renders 0s / 0%, no crash
  - Test: `history` rows include delete %
- [x] **5. End-to-end smoke test** (manual) — type a known string, delete part of
  it with backspaces and one Ctrl+Backspace; confirm added/deleted/% match the
  hand count (± the word-delete estimate).
  (passed 2026-06-10: typed `helloworld` + Backspace ×3 + Ctrl+Backspace ×1 →
  Typed=10, Deleted=8, Delete %=80.0%, Net=2; word-delete estimate applied as
  expected. Note: stale running process must be restarted to pick up new builds.)

## v4 Build Order — system-tray daily driver
A tray icon so the tracker runs alongside work without a terminal. **Storage-free
for now** (live-only; sessions discarded on stop — see Decisions). Keeps the
console `run` untouched and adds a separate `tray` subcommand. New deps:
`pystray`, `Pillow` (first beyond pynput).

- UX: grey icon = idle, red = recording. The hotkey (Ctrl+Alt+B) and a menu
  `Start/Stop recording` both toggle. Tooltip + disabled menu lines show live
  stats (typed / delete % / duration). Stop shows the summary as a notification,
  then discards. Quit stops the hook and the icon cleanly.

- [ ] **1. Tray tooltip/stat formatter** (`reporter.py`) — pure
  `format_tray_tooltip(stats, recording)` → one short line.
  - Test: idle → "idle" text, no counts
  - Test: recording → includes typed, delete %, duration
  - Test: zero-activity recording → sane (0 / 0%), no crash
- [ ] **2. Runtime icon images** (`tray.py`) — Pillow-drawn idle/recording
  circles; no asset files shipped. Add `pystray`/`Pillow` to `pyproject.toml`.
  - Test: returns an image of the expected size/mode for each state
- [ ] **3. Tray controller** (`tray.py`) — thin class binding `App` (with
  `storage=None`) to an injected icon: builds the menu (Start/Stop, stat lines,
  Quit), toggles under a `threading.Lock`, refreshes tooltip/menu from app state.
  The icon is injected so the logic is testable with a fake.
  - Test: menu Start/Stop label flips with `app.recording`
  - Test: the menu toggle action calls the app toggle
  - Test: tooltip / stat lines reflect current app stats (fake icon)
  - Test: stop produces the summary text used for the notification
- [ ] **4. Wire-up + `tray` subcommand** (`__main__.py`, `tray.py`) — `python -m
  code_backtrack tray` starts the pynput listener, an updater daemon (~1s), and
  `icon.run()` on the main thread; Quit / Ctrl+C stop both. Console `run` and the
  bare invocation are unchanged.
  - Test: parser routes `tray` to the tray entry (entry mocked, no real icon)
  - Test: bare invocation + `run`/`history`/etc. still behave as before
- [ ] **5. End-to-end smoke test** (manual) — launch `tray`; icon appears idle;
  hotkey + menu both start/stop; tooltip updates live; recording icon turns red;
  stop shows the summary notification; Quit exits cleanly.

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
- **v2.5 overtype trigger** (*superseded by v3*): printable characters + Enter
  replaced a live selection (counted OVERTYPE). Tab stayed OTHER.
- **v2.5 reporter**: OVERTYPE/CUT appear in the session summary only; the live status
  line stays compact with the original five categories.
- **v3 retires the overtype heuristic**: the v2.5 keyboard-selection state machine
  was removed — a printable key now always counts as CHAR. The heuristic could
  *mis-divert* a normal typed character into OVERTYPE (false-positive selection
  guess), under-counting "Typed (added)"; its magnitude was never measurable anyway.
  Net effect: a more trustworthy added-char count. CUT and CTRL_Z are unaffected.
  The OVERTYPE enum member, DB column, and reporter label are kept (no longer
  produced) so previously-saved sessions still load and display.
- **v3 char metric**: the headline becomes chars added vs deleted + delete %. The
  per-category counts were technically correct but never added up to one readable
  signal; the character view answers "how much of what I type do I delete."
- **v3 stays a counter**: magnitudes come from counting events, not reading text —
  single Backspace/Delete = 1 char (exact), word deletes = fixed estimate. The
  keylogger line (read the document/clipboard) is **not** crossed. Considered and
  rejected: even with instant-wipe, reading text trades a categorical privacy
  guarantee for a policy one, and accessibility APIs are unreliable in the editors
  that matter (VS Code, terminals) anyway.
- **v3 word-delete estimate**: `WORD_DELETE_CHARS = 5` (avg word length). Used for
  Ctrl+Backspace and Ctrl+Delete. Rare in practice; tunable single constant.
- **v3 added = content only**: Space/Enter/Tab are NOT counted as added characters —
  the metric is about typed *content*, and whitespace would inflate "added" and
  deflate the delete %.
- **v4 tray does not persist (for now)**: tray mode runs with no storage —
  sessions are live-only and discarded on stop (summary shown via notification, no
  save prompt). `App` already supports this via `storage=None`. Sidesteps the
  GUI save-dialog question and needs no `tkinter`. Console `run` keeps its opt-in
  SQLite saving; only the tray front-end is storage-free. Revisit if persistent
  tray sessions are wanted later.

## Open Questions
- (none open)

## Dropped (considered, not pursued)
- **Trend charts** and **burst detection** (rewrite vs typo from N+ consecutive
  backspaces) — were planned for v4 but dropped as not wanted. v4 is the tray icon
  only.

## Notes
- v1 counts everywhere; the user controls data quality by only running it while coding.
  Per-app filtering arrives in v2.
- Privacy principle: no key identities or sequences are ever written to disk — only
  category counts and timestamps.
