"""CLI helpers for ``llmwiki synthesize`` extracted from cli.py
(#691 / #arch-h8).

These two helpers (`list_pending`, `complete`) wrap
``llmwiki.synth.agent_delegate`` for the ``--list-pending`` and
``--complete <uuid>`` command-line subactions. They're synth-domain
logic with file I/O + stdin handling, not argparse glue, so they
move out of ``cli.py``. ``cli.py`` re-exports under the original
underscored names for back-compat.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llmwiki import REPO_ROOT


def list_pending() -> int:
    """Print the pending-prompts table for ``--list-pending``.

    Two-column layout: uuid │ slug · project · date. Exit 0 even when
    empty — the slash-command layer treats "nothing pending" as a
    success signal.
    """
    from llmwiki.synth.agent_delegate import list_pending as _list_pending

    rows = _list_pending()
    if not rows:
        print("No pending prompts.")
        return 0
    # Max-width uuid column for alignment.
    uuid_w = max(len(r["uuid"]) for r in rows)
    print(f"{'UUID':<{uuid_w}}  SLUG · PROJECT · DATE")
    print(f"{'-' * uuid_w}  " + "-" * 40)
    for r in rows:
        meta = " · ".join(
            part for part in (r["slug"], r["project"], r["date"]) if part
        )
        print(f"{r['uuid']:<{uuid_w}}  {meta}")
    print(f"\n{len(rows)} pending prompt(s).")
    return 0


def complete(args: argparse.Namespace) -> int:
    """Rewrite a placeholder wiki page with the agent's synthesis.

    Reads the synthesized body from ``args.body`` (file) or stdin,
    calls :func:`llmwiki.synth.agent_delegate.complete_pending` to
    replace the sentinel + prompt-file pair with the real content.

    Exit codes:

    * ``0`` — success
    * ``1`` — missing --page, uuid mismatch, missing sentinel, or I/O
      error
    """
    from llmwiki.synth.agent_delegate import complete_pending

    if not args.page:
        print("error: --complete requires --page <path>", file=sys.stderr)
        return 1

    page_path = Path(args.page)
    if not page_path.is_absolute():
        page_path = REPO_ROOT / page_path

    if args.body:
        body_path = Path(args.body)
        if not body_path.is_absolute():
            body_path = REPO_ROOT / body_path
        try:
            body = body_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"error: reading --body {body_path}: {e}", file=sys.stderr)
            return 1
    else:
        body = sys.stdin.read()
        if not body:
            print(
                "error: --complete expects a body on stdin or via --body",
                file=sys.stderr,
            )
            return 1

    try:
        complete_pending(args.complete, body, page_path)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"completed: {page_path}")
    return 0
