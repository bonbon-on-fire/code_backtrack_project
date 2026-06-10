"""Entry point: python -m code_backtrack [run|history|apps|list|delete] [--db PATH]."""

from __future__ import annotations

import argparse

from .reporter import render_apps, render_history, render_list
from .storage import Storage


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=None, help="override the database path")

    parser = argparse.ArgumentParser(prog="code-backtrack", parents=[common])
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", parents=[common], help="run the tracker (default)")
    sub.add_parser("history", parents=[common], help="list saved sessions with stats")
    sub.add_parser("apps", parents=[common], help="per-app correction breakdown")
    sub.add_parser("list", parents=[common], help="bare list of stored sessions")
    delete = sub.add_parser("delete", parents=[common], help="delete a session by date-time")
    delete.add_argument(
        "when",
        nargs="*",
        help="session date-time as shown by list, e.g. 2026-06-06 13:33 (prefix ok)",
    )
    delete.add_argument("--all", action="store_true", help="delete every stored session")
    return parser


def _delete(storage: Storage, when_parts: list[str], delete_all: bool) -> str:
    if delete_all:
        count = storage.delete_all()
        return f"deleted {count} session{'s' if count != 1 else ''}"
    if not when_parts:
        return "tell me which session: a date-time from 'list' (prefix ok), or --all"
    needle = " ".join(when_parts)
    matches = [
        r for r in storage.load_sessions() if r.started_at.replace("T", " ").startswith(needle)
    ]
    if not matches:
        return f"no session starting with '{needle}' - see 'list'"
    if len(matches) > 1:
        shown = "\n".join(f"  {r.started_at.replace('T', ' ')}" for r in matches)
        return f"'{needle}' matches {len(matches)} sessions - be more specific:\n{shown}"
    storage.delete_session(matches[0].id)
    return f"deleted session {matches[0].started_at.replace('T', ' ')}"


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    command = args.command or "run"
    if command == "run":
        from .app import run  # imports pynput; keep data commands usable without a hook

        run()
        return
    storage = Storage(args.db)
    if command == "history":
        print(render_history(storage.load_sessions()))
    elif command == "apps":
        print(render_apps(storage.load_sessions()))
    elif command == "list":
        print(render_list(storage.load_sessions()))
    elif command == "delete":
        print(_delete(storage, args.when, args.all))


if __name__ == "__main__":
    main()
