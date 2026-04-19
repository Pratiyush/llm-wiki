"""Guardrail: every shipped command must be documented (v1.2.0 · #265).

- Every CLI subcommand registered in ``llmwiki.cli.build_parser`` must
  appear as an ``## subcommand`` heading in ``docs/reference/cli.md``.
- Every `.claude/commands/*.md` file must appear as an
  ``### /slash-command`` heading in ``docs/reference/slash-commands.md``.
- Every top-level nav item in ``llmwiki/build.py`` must appear as a
  row in ``docs/reference/ui.md``.

When a maintainer adds a new subcommand / slash command / nav tab, these
tests fail with a clear message pointing at the missing entry.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT


CLI_REF = REPO_ROOT / "docs" / "reference" / "cli.md"
SLASH_REF = REPO_ROOT / "docs" / "reference" / "slash-commands.md"
UI_REF = REPO_ROOT / "docs" / "reference" / "ui.md"
CLAUDE_CMDS_DIR = REPO_ROOT / ".claude" / "commands"
BUILD_PY = REPO_ROOT / "llmwiki" / "build.py"


# ─── CLI coverage ─────────────────────────────────────────────────────


def _all_cli_subcommands() -> set[str]:
    """Walk the argparse tree + return every subcommand name."""
    from llmwiki.cli import build_parser

    parser = build_parser()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            return set(action.choices.keys())
    raise AssertionError("no subparsers found on the CLI parser")


def test_cli_reference_covers_every_subcommand():
    cli_text = CLI_REF.read_text(encoding="utf-8")

    # CLI reference uses `## <subcommand> — …` headings.
    documented = set(
        re.findall(r"^##\s+`([A-Za-z0-9_-]+)`\s*—", cli_text, re.MULTILINE)
    )
    live = _all_cli_subcommands()

    missing = live - documented
    assert not missing, (
        f"docs/reference/cli.md is missing entries for these shipped "
        f"subcommands: {sorted(missing)}. Add a `## \\`name\\` — …` heading."
    )

    # Warn on documented-but-removed entries (catches drift the other way).
    orphaned = documented - live
    assert not orphaned, (
        f"docs/reference/cli.md documents these subcommands but "
        f"build_parser no longer registers them: {sorted(orphaned)}"
    )


def test_every_cli_subcommand_gets_an_example():
    """Every documented subcommand section must contain at least one
    fenced-bash example — pure prose docs are useless without a
    runnable example."""
    cli_text = CLI_REF.read_text(encoding="utf-8")
    sections = re.split(
        r"^##\s+`([A-Za-z0-9_-]+)`\s*—", cli_text, flags=re.MULTILINE
    )
    # sections = [preamble, name1, body1, name2, body2, …]
    pairs = list(zip(sections[1::2], sections[2::2]))
    missing_examples: list[str] = []
    for name, body in pairs:
        # Every section must have at least one ```bash fence
        if "```bash" not in body:
            missing_examples.append(name)
    assert not missing_examples, (
        f"docs/reference/cli.md subcommand sections missing a ```bash "
        f"example: {missing_examples}"
    )


# ─── Slash command coverage ───────────────────────────────────────────


def _all_slash_commands() -> set[str]:
    if not CLAUDE_CMDS_DIR.is_dir():
        return set()
    return {p.stem for p in CLAUDE_CMDS_DIR.glob("*.md")}


def test_slash_reference_covers_every_command():
    slash_text = SLASH_REF.read_text(encoding="utf-8")

    # Accept h3 headings in any of these shapes:
    #   ### /name
    #   ### `/name`
    #   ### `/name <positional>`
    # The regex captures the bare name (no backticks, no slash, no args).
    documented = set(
        re.findall(
            r"^###\s+`?/([a-z][a-z0-9-]*)",
            slash_text,
            re.MULTILINE,
        )
    )

    live = _all_slash_commands()

    missing = live - documented
    assert not missing, (
        f"docs/reference/slash-commands.md is missing entries for these "
        f"shipped commands: {sorted(missing)}"
    )


def test_slash_reference_counts_correctly():
    """The summary table at the top of the slash ref claims a total
    count — keep it honest."""
    slash_text = SLASH_REF.read_text(encoding="utf-8")
    live_count = len(_all_slash_commands())
    # Look for `**N commands in` — the summary line.
    m = re.search(r"\*\*(\d+)\s+commands?\s+in", slash_text)
    assert m, "slash-commands.md should have a `**N commands in …**` summary"
    claimed = int(m.group(1))
    assert claimed == live_count, (
        f"slash-commands.md says {claimed} commands but there are "
        f"actually {live_count} .md files in .claude/commands/"
    )


# ─── UI coverage ─────────────────────────────────────────────────────


# Nav entries we declared in build.py. Adding a `{link(…)}` that isn't
# listed here will fail — update the list AND the UI reference.
EXPECTED_NAV_KEYS = {
    "home", "projects", "sessions", "models", "vs",
    "graph", "docs", "prototypes", "changelog",
}


def test_build_py_nav_keys_match_expected_set():
    """The UI reference table is ordered by these keys — if build.py
    adds or removes a link, the check below flags it so we update
    both sides of the contract."""
    src = BUILD_PY.read_text(encoding="utf-8")
    # Matches {link("…", "…", "<key>")}
    keys = set(
        re.findall(r'\{link\("[^"]+",\s*"[^"]+",\s*"([^"]+)"\)\}', src)
    )
    missing = EXPECTED_NAV_KEYS - keys
    extra = keys - EXPECTED_NAV_KEYS
    assert not missing, (
        f"build.py nav lost these keys (also update docs/reference/ui.md): {missing}"
    )
    assert not extra, (
        f"build.py nav added new keys — document them in "
        f"docs/reference/ui.md + update this test: {extra}"
    )


def test_ui_reference_lists_every_nav_item():
    ui_text = UI_REF.read_text(encoding="utf-8")
    for label in (
        "Home", "Projects", "Sessions", "Models", "Compare",
        "Graph", "Docs", "Prototypes", "Changelog",
    ):
        assert f"**{label}**" in ui_text, (
            f"docs/reference/ui.md missing nav entry for `{label}`"
        )


def test_ui_reference_documents_command_palette():
    ui_text = UI_REF.read_text(encoding="utf-8")
    # The palette is the most-used UI feature; guard it explicitly.
    for keyword in ("⌘K", "command palette", "fuzzy"):
        assert keyword.lower() in ui_text.lower(), (
            f"ui.md should document the command palette ({keyword})"
        )


def test_ui_reference_documents_keyboard_shortcuts():
    ui_text = UI_REF.read_text(encoding="utf-8")
    for shortcut in ("g h", "g p", "g s", "⌘K"):
        assert shortcut in ui_text, (
            f"ui.md should document keyboard shortcut `{shortcut}`"
        )


# ─── Cross-linking ───────────────────────────────────────────────────


def test_hub_links_to_all_three_new_references():
    hub = (REPO_ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    for target in (
        "reference/cli.md",
        "reference/slash-commands.md",
        "reference/ui.md",
    ):
        assert target in hub, (
            f"docs/index.md should link to {target}"
        )
