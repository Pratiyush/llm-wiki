"""Tests for #383 — complete CLI build chain (``all --with-synth`` + status hint)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_all_parser_accepts_with_synth_flag():
    from llmwiki.cli import build_parser

    args = build_parser().parse_args(["all", "--with-synth", "--synth-force"])
    assert args.with_synth is True
    assert args.synth_force is True


def test_synthesis_status_hint_for_dummy_backend():
    from llmwiki.config_schedule import synthesis_status_hint

    hint = synthesis_status_hint("dummy")
    assert hint is not None
    assert "dummy" in hint
    assert "llmwiki all --with-synth" in hint


def test_synthesis_status_hint_for_ollama_backend():
    from llmwiki.config_schedule import synthesis_status_hint

    hint = synthesis_status_hint("ollama")
    assert hint is not None
    assert "ollama" in hint
    assert "llmwiki synthesize" in hint


def test_cmd_all_with_synth_runs_synthesize_first():
    from llmwiki import cli

    order: list[str] = []

    def make_stub(name: str):
        def _stub(_args):
            order.append(name)
            return 0
        return _stub

    base = {
        "out": Path("/tmp/site-test"),
        "search_mode": "auto",
        "skip_graph": True,
        "graph_engine": "builtin",
        "strict": False,
        "fail_fast": False,
        "with_synth": True,
        "synth_force": False,
        "vault": None,
    }
    args = argparse.Namespace(**base)

    with patch.object(cli, "cmd_synthesize", side_effect=make_stub("synthesize")):
        with patch.object(cli, "cmd_build", side_effect=make_stub("build")):
            with patch.object(cli, "cmd_export", side_effect=make_stub("export")):
                with patch.object(cli, "cmd_lint", side_effect=make_stub("lint")):
                    rc = cli.cmd_all(args)

    assert rc == 0
    assert order[0] == "synthesize"
    assert order[1:] == ["build", "export", "lint"]


def test_cmd_all_with_synth_fail_fast_stops_after_synth_failure():
    from llmwiki import cli

    synth_fail = MagicMock(return_value=1)
    build_stub = MagicMock(return_value=0)
    base = {
        "out": Path("/tmp/site-test"),
        "search_mode": "auto",
        "skip_graph": True,
        "graph_engine": "builtin",
        "strict": False,
        "fail_fast": True,
        "with_synth": True,
        "synth_force": False,
        "vault": None,
    }
    args = argparse.Namespace(**base)

    with patch.object(cli, "cmd_synthesize", synth_fail):
        with patch.object(cli, "cmd_build", build_stub):
            with patch.object(cli, "cmd_export", MagicMock(return_value=0)):
                with patch.object(cli, "cmd_lint", MagicMock(return_value=0)):
                    rc = cli.cmd_all(args)

    assert rc == 1
    assert synth_fail.call_count == 1
    assert build_stub.call_count == 0


def test_sync_status_prints_synthesis_hint(capsys, tmp_path, monkeypatch):
    from llmwiki import cli as cli_mod
    from llmwiki.convert import DEFAULT_STATE_FILE

    monkeypatch.setattr(
        "llmwiki.config_schedule.load_synthesis_backend",
        lambda *a, **k: "dummy",
    )
    DEFAULT_STATE_FILE.write_text('{"_meta": {"last_sync": "2026-04-01T00:00:00Z"}}', encoding="utf-8")

    rc = cli_mod.cmd_sync_status(argparse.Namespace(recent=0))
    out = capsys.readouterr().out

    assert rc == 0
    assert "Hint:" in out
    assert "dummy" in out
