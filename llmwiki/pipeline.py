"""End-to-end build pipeline orchestrator (#691 / #arch-h8).

Pre-#691 ``cmd_all`` lived inside ``cli.py`` and was a 110-LOC
pipeline runner that constructed argparse Namespaces by hand and
dispatched to the cmd_* functions. The architect-agent flagged it as
domain logic that didn't belong in a CLI shim.

The function moves here. ``cli.py`` re-exports it as ``cmd_all`` so
existing callers and the argparse `func=` set_defaults continue to
work unchanged. The cmd_* dispatch targets are imported lazily
inside the function to avoid a circular import (cli.py imports this
module at top, this module would otherwise import cli.py).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Optional

from llmwiki import REPO_ROOT


def run_pipeline(args: argparse.Namespace) -> int:
    """Run the full wiki pipeline end-to-end: build → graph → export all → lint.

    This is the convenience entry point advertised as ``wiki-all`` in
    docs and slash commands. It executes the usual post-sync steps in
    the canonical order so a single command reproduces a CI-ready
    site.

    Exit codes:
      0  every step succeeded (lint warnings are informational).
      1  at least one step returned a non-zero exit status.
      2  ``--strict`` was passed and lint reported any error or warning.
    """
    # #py-h4 (#583): direct dispatch instead of round-tripping through
    # argparse. Each step's Namespace is constructed with the defaults
    # the relevant cmd_* expects; no global parser involvement.
    # cmd_* are lazy-imported here to avoid a circular import — cli.py
    # imports run_pipeline at module top.
    from llmwiki.cli import cmd_build, cmd_export, cmd_graph, cmd_lint

    def _ns(**kw: Any) -> argparse.Namespace:
        return argparse.Namespace(**kw)

    steps: list[tuple[str, str, argparse.Namespace]] = []
    steps.append((
        "build",
        f"build --out {args.out} --search-mode {args.search_mode}",
        _ns(
            out=args.out,
            synthesize=False,
            claude="",
            search_mode=args.search_mode or "auto",
            seed_project_stubs=False,
            vault=None,
        ),
    ))
    if not args.skip_graph:
        steps.append((
            "graph",
            f"graph --format both --engine {args.graph_engine}",
            _ns(format="both", engine=args.graph_engine),
        ))
    steps.append((
        "export",
        f"export all --out {args.out}",
        _ns(format="all", out=args.out, topic=""),
    ))
    # ``lint --fail-on-errors`` so error-severity issues already fail the step;
    # ``--strict`` additionally escalates warnings (checked below).
    lint_label = "lint --fail-on-errors" if args.strict else "lint"
    steps.append((
        "lint",
        lint_label,
        _ns(
            wiki_dir=None,
            rules=None,
            include_llm=False,
            json=False,
            fail_on_errors=args.strict,
        ),
    ))

    dispatch = {
        "build": cmd_build,
        "graph": cmd_graph,
        "export": cmd_export,
        "lint": cmd_lint,
    }

    overall_rc = 0
    lint_rc: Optional[int] = None
    for name, label, sub_args in steps:
        print(f"\n==> llmwiki {label}")
        rc = dispatch[name](sub_args)
        if name == "lint":
            lint_rc = rc
            continue  # lint's own exit policy is handled below
        if rc != 0:
            overall_rc = rc if overall_rc == 0 else overall_rc
            if args.fail_fast:
                print(f"error: step '{name}' exited {rc}; stopping (--fail-fast).", file=sys.stderr)
                return rc

    if args.strict:
        # ``--strict`` escalates *any* lint signal — errors OR warnings —
        # into a pipeline failure. Re-read the lint report directly so we
        # don't depend on lint's own exit code, which by design only fires
        # on error-severity issues.
        from llmwiki.lint import load_pages, run_all, summarize
        wiki_dir = REPO_ROOT / "wiki"
        if wiki_dir.is_dir():
            pages = load_pages(wiki_dir)
            issues = run_all(pages)
            counts = summarize(issues) if issues else {}
            errors = counts.get("error", 0)
            warnings = counts.get("warning", 0)
            if errors or warnings:
                print(
                    f"error: --strict: lint reported "
                    f"{errors} error(s) + {warnings} warning(s).",
                    file=sys.stderr,
                )
                return 2

    if lint_rc not in (None, 0) and overall_rc == 0:
        overall_rc = lint_rc

    return overall_rc
