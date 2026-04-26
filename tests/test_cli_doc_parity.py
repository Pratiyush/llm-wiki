"""Tests for #494 — README CLI table must list real subcommands only.

The bug: README.md advertised `llmwiki watch` and `llmwiki
export-obsidian` long after both were removed in v1.2.0. New users
ran them, hit `unrecognized arguments`, lost trust.

This test parses the README's CLI fenced block, extracts every
`llmwiki <subcommand>` line, and asserts each one is registered as
a subparser in `cli.py:build_parser()`. CI will fail any future PR
that adds a stale entry.
"""

from __future__ import annotations

import re
from pathlib import Path

from llmwiki.cli import build_parser

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

# Match `llmwiki <name>` at start of a line inside the CLI fenced block.
_LINE_RE = re.compile(r"^llmwiki\s+([a-z][a-z0-9-]*)\b", re.MULTILINE)


def _collect_real_subcommands() -> set[str]:
    """Return the set of registered subparser names."""
    parser = build_parser()
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            return set(action.choices)
    raise AssertionError("could not locate subparsers on build_parser()")


def _collect_readme_subcommands() -> set[str]:
    text = README.read_text(encoding="utf-8")
    m = re.search(r"## CLI reference\b.*?(?=\n## |\Z)", text, re.DOTALL)
    assert m, "could not find '## CLI reference' section in README"
    block = m.group(0)
    # Drop the `llmwiki version` line — it's a flag/subcommand convention,
    # may not have its own subparser.
    return {name for name in _LINE_RE.findall(block) if name != "version"}


def test_every_readme_cli_line_maps_to_a_real_subparser():
    """Every `llmwiki <name>` in README.md must exist as a real
    subparser. Closes #494."""
    real = _collect_real_subcommands()
    advertised = _collect_readme_subcommands()
    phantom = advertised - real
    assert not phantom, (
        f"README CLI table advertises subcommands that don't exist: "
        f"{sorted(phantom)}. Real subparsers: {sorted(real)}. "
        f"Either wire up the missing subparsers in cli.py:build_parser() or "
        f"remove the lines from README.md (the original bug, #494)."
    )
