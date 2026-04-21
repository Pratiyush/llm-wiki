"""Tests for shell completion (v1.1.0, #216)."""

from __future__ import annotations

import pytest

from llmwiki.completion import (
    bash_script,
    zsh_script,
    fish_script,
    generate,
    GENERATORS,
)


# ─── registry ─────────────────────────────────────────────────────────


def test_three_shells_supported():
    assert set(GENERATORS.keys()) == {"bash", "zsh", "fish"}


# ─── dispatcher ──────────────────────────────────────────────────────


def test_generate_bash():
    script = generate("bash")
    assert isinstance(script, str)
    assert "bash completion for llmwiki" in script


def test_generate_zsh():
    script = generate("zsh")
    assert script.startswith("#compdef llmwiki")


def test_generate_fish():
    script = generate("fish")
    assert "fish completion for llmwiki" in script


def test_generate_invalid_shell():
    with pytest.raises(ValueError, match="unknown shell"):
        generate("powershell")


# ─── bash ────────────────────────────────────────────────────────────


def test_bash_registers_completion():
    script = bash_script()
    assert "complete -F _llmwiki llmwiki" in script


def test_bash_defines_function():
    script = bash_script()
    assert "_llmwiki()" in script


def test_bash_includes_every_subcommand():
    script = bash_script()
    # All key subcommands must appear in the WORD list
    for sub in ["sync", "build", "serve", "init", "version",
                "adapters", "graph", "watch", "link-obsidian",
                "install-skills", "lint", "check-links"]:
        assert sub in script, f"missing subcommand: {sub}"


def test_bash_handles_cword_1():
    """cword == 1 means "which subcommand?" — complete against the sub list."""
    script = bash_script()
    assert 'cword" -eq 1' in script


# ─── zsh ─────────────────────────────────────────────────────────────


def test_zsh_compdef_directive():
    script = zsh_script()
    assert script.startswith("#compdef llmwiki")


def test_zsh_describes_subcommands():
    script = zsh_script()
    assert "_describe 'subcommand'" in script


def test_zsh_includes_subcommands():
    script = zsh_script()
    for sub in ["sync", "build", "serve", "lint"]:
        assert sub in script


# ─── fish ────────────────────────────────────────────────────────────


def test_fish_has_subcommand_completions():
    script = fish_script()
    assert "__fish_use_subcommand" in script


def test_fish_has_flag_completions():
    script = fish_script()
    assert "__fish_seen_subcommand_from" in script


def test_fish_includes_every_subcommand():
    script = fish_script()
    for sub in ["sync", "build", "serve", "init", "lint",
                "link-obsidian", "install-skills", "completion"]:
        assert f"-a '{sub}'" in script


def test_fish_completes_flags_for_sync():
    script = fish_script()
    # sync has --auto-build, --auto-lint, --dry-run, --force, --download-images, etc.
    assert "-n '__fish_seen_subcommand_from sync'" in script


# ─── CLI integration ────────────────────────────────────────────────


def test_cli_completion_subcommand_exists():
    """`llmwiki completion` subcommand is registered."""
    from llmwiki.cli import build_parser
    parser = build_parser()
    # Walk subparsers to confirm "completion" exists
    sub_action = None
    for a in parser._actions:
        if hasattr(a, "choices") and a.choices:
            sub_action = a
            break
    assert sub_action is not None
    assert "completion" in sub_action.choices
