"""Tests for #470 — `llmwiki sync --vault PATH` must actually write
into the vault.

Bug: cmd_sync printed the banner, validated the path, then called
convert_all() with no out_dir / state_file. Every session wrote to
the repo's raw/sessions/ instead of the vault — silent data
routing failure.

Fix: when --vault is given, route out_dir, state_file, auto_build
site root, and auto_lint wiki dir into the vault.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_args(**overrides):
    """Build an argparse Namespace with cmd_sync's expected fields."""
    base = {
        "vault": None,
        "allow_overwrite": False,
        "adapter": None,
        "since": None,
        "project": None,
        "include_current": False,
        "force": False,
        "auto_build": False,
        "auto_lint": False,
        "status": False,
        "recent": 0,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _capture_convert_all_kwargs():
    captured: dict = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        return 0

    return captured, _fake


def test_vault_sync_routes_out_dir_into_vault(tmp_path: Path):
    """Original bug: sessions wrote to REPO_ROOT/raw/sessions/ instead
    of vault/raw/sessions/."""
    from llmwiki.cli import cmd_sync

    vault = tmp_path / "myvault"
    vault.mkdir()

    captured, fake_convert_all = _capture_convert_all_kwargs()
    with patch("llmwiki.convert.convert_all", side_effect=fake_convert_all):
        cmd_sync(_make_args(vault=vault))

    assert "out_dir" in captured
    assert captured["out_dir"] == vault.resolve() / "raw" / "sessions"


def test_vault_sync_routes_state_file_into_vault(tmp_path: Path):
    """State must live in the vault — same #420 isolation principle."""
    from llmwiki.cli import cmd_sync

    vault = tmp_path / "myvault"
    vault.mkdir()

    captured, fake_convert_all = _capture_convert_all_kwargs()
    with patch("llmwiki.convert.convert_all", side_effect=fake_convert_all):
        cmd_sync(_make_args(vault=vault))

    assert captured.get("state_file") == vault.resolve() / ".llmwiki-state.json"


def test_default_no_vault_behaviour_unchanged(tmp_path: Path):
    """Without --vault, default paths must be honoured unchanged."""
    from llmwiki.cli import cmd_sync
    from llmwiki.convert import DEFAULT_OUT_DIR, DEFAULT_STATE_FILE

    captured, fake_convert_all = _capture_convert_all_kwargs()
    with patch("llmwiki.convert.convert_all", side_effect=fake_convert_all):
        cmd_sync(_make_args())

    assert captured.get("out_dir") == DEFAULT_OUT_DIR
    assert captured.get("state_file") == DEFAULT_STATE_FILE


def test_force_with_vault_uses_vault_state_file(tmp_path: Path):
    """--force --vault must still write to the vault state, not the
    repo state. Otherwise the next plain --vault sync re-processes
    everything (the very thing #426 fixed for the non-vault case)."""
    from llmwiki.cli import cmd_sync

    vault = tmp_path / "v"
    vault.mkdir()

    captured, fake_convert_all = _capture_convert_all_kwargs()
    with patch("llmwiki.convert.convert_all", side_effect=fake_convert_all):
        cmd_sync(_make_args(vault=vault, force=True))

    assert captured.get("force") is True
    assert captured.get("state_file") == vault.resolve() / ".llmwiki-state.json"


def test_vault_auto_build_writes_site_to_vault(tmp_path: Path):
    """When --auto-build is on, the site lands in the vault."""
    from llmwiki.cli import cmd_sync

    vault = tmp_path / "v"
    vault.mkdir()

    build_call: dict = {}

    def fake_build_site(**kwargs):
        build_call.update(kwargs)
        return 0

    with patch("llmwiki.convert.convert_all", return_value=0), \
         patch("llmwiki.build.build_site", side_effect=fake_build_site), \
         patch("llmwiki.cli._should_run_after_sync", return_value=True), \
         patch("llmwiki.cli._load_schedule_config", return_value={"build": "on-sync"}):
        cmd_sync(_make_args(vault=vault, auto_build=True))

    assert build_call.get("out_dir") == vault.resolve() / "site"


def test_vault_auto_lint_uses_vault_wiki(tmp_path: Path):
    """When --auto-lint is on, lint reads the vault's wiki."""
    from llmwiki.cli import cmd_sync

    vault = tmp_path / "v"
    (vault / "wiki").mkdir(parents=True)

    lint_call: dict = {}

    def fake_load_pages(wiki_dir=None):
        lint_call["wiki_dir"] = wiki_dir
        return {}

    with patch("llmwiki.convert.convert_all", return_value=0), \
         patch("llmwiki.lint.load_pages", side_effect=fake_load_pages), \
         patch("llmwiki.lint.run_all", return_value=[]), \
         patch("llmwiki.lint.summarize", return_value={}), \
         patch("llmwiki.cli._should_run_after_sync", return_value=True), \
         patch("llmwiki.cli._load_schedule_config", return_value={"lint": "on-sync"}):
        cmd_sync(_make_args(vault=vault, auto_lint=True))

    assert lint_call.get("wiki_dir") == vault.resolve() / "wiki"


def test_nonexistent_vault_path_returns_error(tmp_path: Path):
    """Passing --vault PATH where PATH doesn't exist still errors-out
    cleanly (regression guard for the existing behaviour)."""
    from llmwiki.cli import cmd_sync

    bogus = tmp_path / "does-not-exist"
    rc = cmd_sync(_make_args(vault=bogus))
    assert rc == 2


def test_vault_sync_does_not_pollute_repo_paths(tmp_path: Path):
    """End-to-end: convert_all gets vault paths, NOT repo defaults."""
    from llmwiki.cli import cmd_sync
    from llmwiki.convert import DEFAULT_OUT_DIR, DEFAULT_STATE_FILE

    vault = tmp_path / "v"
    vault.mkdir()

    captured, fake_convert_all = _capture_convert_all_kwargs()
    with patch("llmwiki.convert.convert_all", side_effect=fake_convert_all):
        cmd_sync(_make_args(vault=vault))

    assert captured["out_dir"] != DEFAULT_OUT_DIR
    assert captured["state_file"] != DEFAULT_STATE_FILE
