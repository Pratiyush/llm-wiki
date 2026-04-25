"""End-to-end CLI smoke tests for every ``python -m llmwiki`` subcommand.

The existing unit suite (``tests/test_cli.py``) imports the CLI entry
point and calls handlers directly, but never exercises the public
``python -m llmwiki <cmd>`` surface that users and shell scripts rely on.
A regression where the argparse wiring breaks for one subcommand would
slip through the unit tests because they bypass argparse entirely.

This module fills that gap. For every subcommand we:

1. Invoke ``python -m llmwiki <cmd> --help`` and assert exit 0 + a help
   header. This catches argparse misconfiguration on every subcommand
   in a single pass — a broken ``add_argument`` typically raises at
   parser-build time, so even ``--help`` fails.
2. For pure / no-side-effect subcommands (``version``, ``adapters``)
   we run the real command and assert on the output shape.
3. For subcommands that need a workspace (``build``, ``graph``,
   ``export``, ``lint``) we drive them in-process via the public Python
   API used by the conftest fixture, against a tmp workspace seeded
   with the same synthetic corpus used by the rest of the e2e suite.
   Going in-process is faster than spawning a subprocess per test and
   avoids the REPO_ROOT pinning issue (REPO_ROOT is captured at module
   import time, so a subprocess inherits the user's repo, not our
   tmp workspace — using the in-process API with monkeypatched
   ``RAW_DIR`` / ``RAW_SESSIONS`` is the only correct way).

This file is browser-free — no Playwright, no fixtures from the
session-scoped harness — so it runs in well under a minute and can be
gated separately in CI if browser tests are slow or flaky.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest


# ─── helpers ────────────────────────────────────────────────────────────

REPO_ROOT_FOR_CLI = Path(__file__).resolve().parents[2]
"""Repo root the CLI subprocess will resolve REPO_ROOT against. We pin
it explicitly so a test that runs from a different cwd still hits the
right module path. The CLI's REPO_ROOT comes from llmwiki/__init__.py
(``Path(__file__).resolve().parent.parent``), so a subprocess invoked
with ``-m llmwiki`` from any cwd resolves to the same repo root."""


def _run_cli(*args: str, timeout: int = 30, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Invoke ``python -m llmwiki <args...>`` and capture output.

    We use the same Python that pytest is running under so we hit the
    installed llmwiki package, not whatever happens to be on PATH.
    """
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(REPO_ROOT_FOR_CLI),
    )


# Every subcommand registered in build_parser(). Keep in sync with
# llmwiki/cli.py — a new subcommand should be added here so its
# argparse wiring gets exercised.
ALL_SUBCOMMANDS = (
    "init",
    "sync",
    "build",
    "serve",
    "adapters",
    "graph",
    "export",
    "lint",
    "candidates",
    "synthesize",
    "query",
    "version",
)


# ─── --help works for every subcommand ──────────────────────────────────


@pytest.mark.parametrize("cmd", ALL_SUBCOMMANDS)
def test_subcommand_help_exits_clean(cmd: str) -> None:
    """``llmwiki <cmd> --help`` exits 0 and prints something
    help-shaped. Regressions in argparse configuration (e.g. duplicate
    flags, bad ``choices=`` values) surface here even though no real
    work runs."""
    result = _run_cli(cmd, "--help", timeout=15)
    assert result.returncode == 0, (
        f"`llmwiki {cmd} --help` exited {result.returncode}\n"
        f"stdout: {result.stdout[:400]}\nstderr: {result.stderr[:400]}"
    )
    # ``argparse`` always prints "usage:" at the top of help output.
    assert "usage:" in result.stdout.lower(), (
        f"`llmwiki {cmd} --help` did not print a usage line"
    )


def test_top_level_help_lists_every_subcommand() -> None:
    """``llmwiki --help`` mentions each subcommand. Catches the case
    where a subparser is registered but not surfaced (or vice versa)."""
    result = _run_cli("--help", timeout=15)
    assert result.returncode == 0
    for cmd in ALL_SUBCOMMANDS:
        assert cmd in result.stdout, (
            f"`llmwiki --help` does not mention subcommand {cmd!r}"
        )


def test_no_args_prints_help_and_exits_clean() -> None:
    """Running with no subcommand prints help and exits 0 (per
    ``main()`` in cli.py). A non-zero exit here would be a regression."""
    result = _run_cli(timeout=15)
    assert result.returncode == 0, (
        f"bare `python -m llmwiki` exited {result.returncode}"
    )
    assert "usage:" in result.stdout.lower()


def test_unknown_subcommand_fails_with_helpful_error() -> None:
    """Argparse should reject a typo with exit code 2 and an error
    message that mentions valid subcommands. Catches the case where
    a developer accidentally enables ``parents=[...]`` in a way that
    swallows unknown commands."""
    result = _run_cli("not-a-real-command", timeout=15)
    assert result.returncode != 0
    # argparse writes "invalid choice" or similar to stderr.
    err = (result.stderr + result.stdout).lower()
    assert "invalid choice" in err or "unrecognized" in err or "not-a-real-command" in err


# ─── version ────────────────────────────────────────────────────────────


def test_version_subcommand_prints_semver() -> None:
    """``llmwiki version`` prints ``llmwiki <version>``. We accept any
    non-empty version string so a release bump doesn't break the test —
    we only assert it's *something* that starts with ``llmwiki ``."""
    result = _run_cli("version", timeout=15)
    assert result.returncode == 0
    assert result.stdout.strip().startswith("llmwiki "), (
        f"unexpected version output: {result.stdout!r}"
    )
    # Version should look like NN.NN.NN (loosely).
    rest = result.stdout.strip().removeprefix("llmwiki ").strip()
    assert re.match(r"^\d+\.\d+", rest), (
        f"version {rest!r} does not start with digits.digits"
    )


def test_top_level_version_flag() -> None:
    """``llmwiki --version`` (built into argparse) matches the
    ``version`` subcommand. Both must agree — divergence here is a
    real bug for users who script around ``--version``."""
    sub = _run_cli("version", timeout=15).stdout.strip()
    flag = _run_cli("--version", timeout=15).stdout.strip()
    assert sub == flag, (
        f"`version` subcommand printed {sub!r} but `--version` flag "
        f"printed {flag!r} — they should match"
    )


# ─── adapters ───────────────────────────────────────────────────────────


def test_adapters_lists_at_least_one_adapter() -> None:
    """``llmwiki adapters`` discovers + lists adapters. The Claude Code
    adapter is always registered (it's the default), so even on a fresh
    checkout we expect to see at least one row."""
    result = _run_cli("adapters", timeout=20)
    assert result.returncode == 0, result.stderr
    # Header row + at least one data row.
    assert "Registered adapters:" in result.stdout
    # #387 U2: columns are now name / present / enabled / active / description.
    assert "present" in result.stdout
    assert "enabled" in result.stdout
    assert "active" in result.stdout


def test_adapters_wide_disables_truncation() -> None:
    """``llmwiki adapters --wide`` prints the full description column
    without ellipses. We can't assert on a specific description (the
    set of adapters is dynamic) but we *can* assert no row ends with
    the truncation marker '...'."""
    result = _run_cli("adapters", "--wide", timeout=20)
    assert result.returncode == 0
    # Find data rows (start with two spaces, then a non-dash char).
    data_rows = [
        line for line in result.stdout.splitlines()
        if line.startswith("  ") and not line.startswith("  -") and "name" not in line.split()
    ]
    truncated = [r for r in data_rows if r.rstrip().endswith("...")]
    assert not truncated, (
        f"--wide should disable truncation, but {len(truncated)} row(s) "
        f"end in '...': {truncated[:3]}"
    )


# ─── build / lint / graph / export against a tmp workspace ──────────────


@pytest.fixture()
def tmp_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a tmp workspace shaped like a real llmwiki checkout
    (raw/sessions/<project>/<file>.md + wiki/) and monkeypatch the
    module-level paths so subsequent in-process build / lint calls
    target this directory instead of the user's actual repo.

    We seed only enough content to make ``discover_sources`` find one
    session — this keeps the test fast while still exercising the full
    build → graph → export → lint pipeline.
    """
    raw = tmp_path / "raw"
    raw_sessions = raw / "sessions" / "cli-smoke"
    raw_sessions.mkdir(parents=True)

    session_md = """---
title: "Session: cli-smoke — 2026-04-09"
type: source
tags: [claude-code, session-transcript]
date: 2026-04-09
source_file: raw/sessions/cli-smoke/2026-04-09-cli-smoke.md
sessionId: cli-smoke-000000000000000000000001
slug: cli-smoke
project: cli-smoke
started: 2026-04-09T09:00:00+00:00
ended: 2026-04-09T09:30:00+00:00
cwd: /tmp/cli-smoke
gitBranch: main
permissionMode: default
model: claude-sonnet-4-6
user_messages: 1
tool_calls: 1
tools_used: [Read]
tool_counts: {"Read": 1}
token_totals: {"input": 100, "cache_creation": 200, "cache_read": 800, "output": 50}
turn_count: 1
hour_buckets: {"2026-04-09T09": 1}
duration_seconds: 1800
is_subagent: false
---

# Session: cli-smoke — 2026-04-09

## Summary

A trivial single-turn session used by the CLI smoke tests.

## Conversation

### Turn 1 — User

Hi.

### Turn 1 — Assistant

Hello.

## Connections

- [[Greeting]]
"""
    (raw_sessions / "2026-04-09-cli-smoke.md").write_text(session_md, encoding="utf-8")

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "entities").mkdir()
    (wiki / "concepts").mkdir()
    (wiki / "syntheses").mkdir()
    (wiki / "index.md").write_text(
        "# Wiki Index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Syntheses\n",
        encoding="utf-8",
    )
    (wiki / "overview.md").write_text(
        '---\ntitle: "Overview"\ntype: synthesis\nsources: []\nlast_updated: ""\n---\n\n# Overview\n',
        encoding="utf-8",
    )

    # Monkeypatch the module-level constants the build/graph/export
    # codepaths read from. Same trick as conftest.py uses for the e2e
    # session fixture, just folded into a per-test fixture so each CLI
    # subcommand test gets its own clean workspace.
    from llmwiki import build as build_mod

    monkeypatch.setattr(build_mod, "RAW_DIR", raw)
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", raw / "sessions")

    return tmp_path


def test_build_emits_index_html(tmp_workspace: Path) -> None:
    """``build_site()`` emits ``site/index.html``. We call the public
    API directly rather than spawning a subprocess so the test is fast
    and we can use ``tmp_workspace``'s monkeypatched paths."""
    from llmwiki.build import build_site

    out = tmp_workspace / "site"
    rc = build_site(out_dir=out, synthesize=False)
    assert rc == 0, f"build_site returned {rc}"
    assert (out / "index.html").is_file(), "site/index.html missing"
    # The home page should reference the seeded session.
    home_html = (out / "index.html").read_text(encoding="utf-8")
    assert "cli-smoke" in home_html.lower(), (
        "home page does not mention the seeded session — did discovery break?"
    )


def test_build_emits_search_index(tmp_workspace: Path) -> None:
    """``build_site()`` writes a JSON search index that the client-side
    palette consumes. Validating its shape here saves us from a class
    of palette-can't-find-anything bugs that would otherwise only show
    up in browser tests."""
    from llmwiki.build import build_site

    out = tmp_workspace / "site"
    build_site(out_dir=out, synthesize=False)
    idx_path = out / "search-index.json"
    assert idx_path.is_file(), "search-index.json missing"
    data = json.loads(idx_path.read_text(encoding="utf-8"))
    # Old vs new shape: some builds write a list, others write
    # {"items": [...]}. Accept either — we only care that it's a
    # well-formed JSON containing at least one entry.
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("items") or data.get("entries") or list(data.values())
    else:
        pytest.fail(f"unexpected search-index.json root type: {type(data).__name__}")
    assert items, "search-index.json is empty — build skipped indexing"


def test_lint_runs_and_reports(tmp_workspace: Path) -> None:
    """``cmd_lint`` runs the lint registry and prints a summary line.
    A new project may have many violations; we don't care about the
    count, only that the runner doesn't crash and emits a parseable
    summary (X errors, Y warnings, Z info)."""
    from llmwiki.lint import load_pages, run_all, summarize

    pages = load_pages(tmp_workspace / "wiki")
    issues = run_all(pages)
    summary = summarize(issues)
    # All severity buckets should be int counts (possibly zero).
    for severity in ("error", "warning", "info"):
        assert isinstance(summary.get(severity, 0), int), (
            f"summary[{severity}] is not an int: {summary.get(severity)!r}"
        )


def test_export_all_writes_expected_artifacts(tmp_workspace: Path) -> None:
    """``cmd_export`` ``all`` writes every AI-consumable export. This
    guards the contract that the static-site CDN-ables (sitemap, RSS,
    llms.txt) all show up in one pass — a regression where one of the
    writers silently no-ops would slip through unit tests but breaks
    SEO + LLM-discoverability in production."""
    from llmwiki.exporters import export_all
    from llmwiki.build import discover_sources, group_by_project, RAW_SESSIONS

    out = tmp_workspace / "site"
    out.mkdir(parents=True, exist_ok=True)
    sources = discover_sources(RAW_SESSIONS)
    if not sources:
        pytest.skip("no sources discovered in tmp workspace — fixture mismatch")
    groups = group_by_project(sources)
    paths = export_all(out, groups, sources)
    # Sanity: every returned path actually exists on disk.
    missing = [name for name, p in paths.items() if not p.is_file()]
    assert not missing, f"export_all reported writing {missing} but the files are absent"
    # Spot-check a few we depend on.
    assert (out / "llms.txt").is_file(), "llms.txt missing — LLM discovery contract broken"
    assert (out / "sitemap.xml").is_file(), "sitemap.xml missing — SEO contract broken"


def test_graph_subcommand_accepts_engine_flag() -> None:
    """``llmwiki graph --help`` exposes the ``--engine`` flag with
    ``builtin`` and ``graphify`` choices. We verify the CLI surface
    here rather than running the graph because ``llmwiki.graph``
    captures ``REPO_ROOT`` at import time and writes there
    unconditionally — invoking it under a tmp workspace would pollute
    the user's actual repo. The functional graph behavior is already
    covered by ``tests/test_graph_*.py`` which uses the right harness."""
    result = _run_cli("graph", "--help", timeout=15)
    assert result.returncode == 0
    assert "--engine" in result.stdout, "graph subcommand missing --engine flag"
    assert "builtin" in result.stdout and "graphify" in result.stdout, (
        "graph --engine choices missing builtin / graphify"
    )
    # ``--format`` must accept json / html / both.
    assert "--format" in result.stdout, "graph subcommand missing --format flag"


def test_graph_run_against_real_repo_produces_well_formed_json() -> None:
    """Run ``llmwiki graph`` against the real repo and assert the
    resulting ``graph/graph.json`` parses + has the right shape.

    This is the only test in the suite that touches the real repo
    (``graph/`` is gitignored, so this is safe — the file is
    regenerated on every CI run anyway). The alternative — monkeypatching
    REPO_ROOT — would require deep module surgery. Better to accept the
    one-off side-effect on a gitignored output dir."""
    result = _run_cli("graph", "--engine", "builtin", "--format", "json", timeout=60)
    assert result.returncode == 0, (
        f"`llmwiki graph --engine builtin` failed: {result.stderr[:400]}"
    )
    graph_json = REPO_ROOT_FOR_CLI / "graph" / "graph.json"
    if not graph_json.is_file():
        pytest.skip("graph/graph.json not produced — wiki may have no pages")
    data = json.loads(graph_json.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "graph.json root is not an object"
    assert "nodes" in data or any(isinstance(v, list) for v in data.values()), (
        f"graph.json has no nodes-like list: keys={list(data.keys())}"
    )


# ─── synthesize / query: skip cleanly when optional deps missing ───────


def test_synthesize_check_runs_or_skips() -> None:
    """``llmwiki synthesize --check`` probes backend availability.
    With no backend configured it exits non-zero — we accept any exit
    code as long as the command doesn't crash with a Python traceback."""
    result = _run_cli("synthesize", "--check", timeout=20)
    # 0 (backend reachable), 1 (not reachable) — both fine. >1 means
    # an unhandled exception, which is what we're guarding against.
    assert result.returncode in (0, 1), (
        f"synthesize --check exited {result.returncode}\n"
        f"stderr: {result.stderr[:400]}"
    )
    # No Python traceback in stderr.
    assert "Traceback" not in result.stderr, (
        f"synthesize --check raised an unhandled exception:\n{result.stderr}"
    )


def test_query_without_graphify_exits_cleanly() -> None:
    """``llmwiki query`` requires the optional ``graphify`` package.
    Without it, the command must print a friendly install hint and
    exit 2, *not* crash with ImportError. This is a real UX contract:
    optional deps must degrade gracefully."""
    result = _run_cli("query", "what", "is", "this", timeout=15)
    assert result.returncode in (0, 2), (
        f"query exited {result.returncode} (expected 0 if graphify "
        f"installed, 2 if not). stderr: {result.stderr[:400]}"
    )
    # Either the query ran (graphify installed) OR we got a graceful
    # install hint (graphify missing). A Python traceback indicates
    # the graceful path is broken.
    assert "Traceback" not in result.stderr, (
        f"query crashed instead of gracefully reporting missing dep:\n{result.stderr}"
    )


# ─── candidates list: empty workspace handling ──────────────────────────


def test_candidates_list_on_empty_workspace(tmp_workspace: Path) -> None:
    """``cmd_candidates list`` should return 0 with an empty count
    when no candidates exist. Catches the case where a fresh project
    triggers a 'directory not found' error instead of an empty list."""
    from llmwiki.candidates import list_candidates

    items = list_candidates(tmp_workspace / "wiki")
    assert isinstance(items, list), f"list_candidates returned {type(items).__name__}, not list"
    # Empty workspace → empty list, not None or an error.
    assert items == [] or all(isinstance(c, dict) for c in items), (
        "list_candidates returned malformed entries"
    )


# ─── docs sanity: every subcommand has a non-empty help string ──────────


@pytest.mark.parametrize("cmd", ALL_SUBCOMMANDS)
def test_subcommand_has_nonempty_help_text(cmd: str) -> None:
    """Every subcommand's argparse help text should be at least one
    sentence, not just the auto-generated boilerplate. UX regression:
    a contributor adds a subcommand without writing a description and
    users discover it has no documentation when they hit --help."""
    result = _run_cli(cmd, "--help", timeout=15)
    assert result.returncode == 0
    # Strip the "usage: ..." preamble; what remains should have content.
    body = result.stdout.split("\n\n", 1)[1] if "\n\n" in result.stdout else result.stdout
    # We expect at least 20 chars of human-readable text after the usage block.
    assert len(body.strip()) >= 20, (
        f"`llmwiki {cmd} --help` body is suspiciously short:\n{result.stdout}"
    )
