"""Tests for the `llmwiki all` orchestrator (closes #422).

Pre-fix, `cmd_all` called `build_parser()` once *per step*, rebuilding
the entire argparse tree four times for a single invocation. That was
wasteful argparse work AND a coupling smell — each subcommand's flag
set leaked into the cmd_all contract via the shared parser. Build the
parser once and re-use the parsed namespace.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch


def _mk_args(**overrides) -> argparse.Namespace:
    """Build a minimal Namespace that cmd_all expects."""
    base = {
        "out": Path("/tmp/site-test"),
        "search_mode": "auto",
        "skip_graph": True,        # don't actually build a graph
        "graph_engine": "builtin",
        "strict": False,
        "fail_fast": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


# ─── Parser-build call counter ───────────────────────────────────────


def test_cmd_all_builds_parser_once_only():
    """Regression for #422: cmd_all must call build_parser() exactly
    once across all steps. Previously called 4× (once per step)."""
    from llmwiki import cli

    call_count = {"n": 0}
    original_build_parser = cli.build_parser

    def counting_build_parser():
        call_count["n"] += 1
        return original_build_parser()

    # Stub each command function so we don't actually execute build/etc.
    stub = MagicMock(return_value=0)

    with patch.object(cli, "build_parser", side_effect=counting_build_parser):
        with patch.object(cli, "cmd_build", stub):
            with patch.object(cli, "cmd_lint", stub):
                with patch("llmwiki.exporters.export_all", stub):
                    with patch.object(cli, "cmd_export", stub):
                        cli.cmd_all(_mk_args())

    assert call_count["n"] == 1, (
        f"cmd_all called build_parser() {call_count['n']} times "
        f"(expected exactly 1 — see #422)"
    )


def test_cmd_all_default_returns_zero():
    """Smoke: with all sub-steps stubbed to succeed, cmd_all returns 0."""
    from llmwiki import cli

    stub = MagicMock(return_value=0)
    with patch.object(cli, "cmd_build", stub):
        with patch.object(cli, "cmd_export", stub):
            with patch.object(cli, "cmd_lint", stub):
                rc = cli.cmd_all(_mk_args())

    assert rc == 0


def test_cmd_all_propagates_failure_when_not_fail_fast():
    """Without --fail-fast, a non-zero step shouldn't abort early but
    the overall exit reflects the failure."""
    from llmwiki import cli

    failing_build = MagicMock(return_value=2)
    succeeding_other = MagicMock(return_value=0)
    with patch.object(cli, "cmd_build", failing_build):
        with patch.object(cli, "cmd_export", succeeding_other):
            with patch.object(cli, "cmd_lint", succeeding_other):
                rc = cli.cmd_all(_mk_args(fail_fast=False))

    # build failed (rc=2); subsequent steps still ran; overall non-zero.
    assert rc != 0
    assert failing_build.call_count == 1
    assert succeeding_other.call_count >= 1  # export + lint both ran


def test_cmd_all_fail_fast_aborts_on_first_failure():
    """With --fail-fast, the first non-zero step short-circuits."""
    from llmwiki import cli

    failing_build = MagicMock(return_value=2)
    other = MagicMock(return_value=0)
    with patch.object(cli, "cmd_build", failing_build):
        with patch.object(cli, "cmd_export", other):
            with patch.object(cli, "cmd_lint", other):
                rc = cli.cmd_all(_mk_args(fail_fast=True))

    assert rc == 2
    assert failing_build.call_count == 1
    # export/lint must NOT have run after the failure.
    assert other.call_count == 0


def test_cmd_all_skip_graph_omits_graph_step():
    """--skip-graph (default in our test) → graph step never invoked."""
    from llmwiki import cli

    graph_stub = MagicMock(return_value=0)
    other = MagicMock(return_value=0)
    with patch.object(cli, "cmd_graph", graph_stub):
        with patch.object(cli, "cmd_build", other):
            with patch.object(cli, "cmd_export", other):
                with patch.object(cli, "cmd_lint", other):
                    rc = cli.cmd_all(_mk_args(skip_graph=True))

    assert rc == 0
    assert graph_stub.call_count == 0


def test_cmd_all_includes_graph_step_when_not_skipped():
    """Without --skip-graph, the graph step runs."""
    from llmwiki import cli

    graph_stub = MagicMock(return_value=0)
    other = MagicMock(return_value=0)
    with patch.object(cli, "cmd_graph", graph_stub):
        with patch.object(cli, "cmd_build", other):
            with patch.object(cli, "cmd_export", other):
                with patch.object(cli, "cmd_lint", other):
                    rc = cli.cmd_all(_mk_args(skip_graph=False))

    assert rc == 0
    assert graph_stub.call_count == 1


def test_cmd_all_strict_propagates_to_lint_argv():
    """--strict adds --fail-on-errors to the lint step's argv."""
    from llmwiki import cli

    received_argvs: list[list[str]] = []
    original = cli.build_parser

    class WrapParser:
        def __init__(self, real):
            self._real = real
        def parse_args(self, argv):
            received_argvs.append(list(argv))
            return self._real.parse_args(argv)

    def fake_build_parser():
        return WrapParser(original())

    stub = MagicMock(return_value=0)
    with patch.object(cli, "build_parser", side_effect=fake_build_parser):
        with patch.object(cli, "cmd_build", stub):
            with patch.object(cli, "cmd_export", stub):
                with patch.object(cli, "cmd_lint", stub):
                    cli.cmd_all(_mk_args(strict=True))

    lint_argv = next((a for a in received_argvs if a and a[0] == "lint"), None)
    assert lint_argv is not None
    assert "--fail-on-errors" in lint_argv


def test_cmd_all_out_dir_propagates_to_steps():
    """--out flows through to build's --out argv."""
    from llmwiki import cli

    received_argvs: list[list[str]] = []
    original = cli.build_parser

    class WrapParser:
        def __init__(self, real):
            self._real = real
        def parse_args(self, argv):
            received_argvs.append(list(argv))
            return self._real.parse_args(argv)

    stub = MagicMock(return_value=0)
    with patch.object(cli, "build_parser", side_effect=lambda: WrapParser(original())):
        with patch.object(cli, "cmd_build", stub):
            with patch.object(cli, "cmd_export", stub):
                with patch.object(cli, "cmd_lint", stub):
                    cli.cmd_all(_mk_args(out=Path("/custom/out")))

    build_argv = next((a for a in received_argvs if a and a[0] == "build"), None)
    assert build_argv is not None
    assert "--out" in build_argv
    out_idx = build_argv.index("--out")
    assert build_argv[out_idx + 1] == "/custom/out"


def test_cmd_all_search_mode_propagates_to_build():
    """--search-mode flows through to build's argv."""
    from llmwiki import cli

    received_argvs: list[list[str]] = []
    original = cli.build_parser

    class WrapParser:
        def __init__(self, real):
            self._real = real
        def parse_args(self, argv):
            received_argvs.append(list(argv))
            return self._real.parse_args(argv)

    stub = MagicMock(return_value=0)
    with patch.object(cli, "build_parser", side_effect=lambda: WrapParser(original())):
        with patch.object(cli, "cmd_build", stub):
            with patch.object(cli, "cmd_export", stub):
                with patch.object(cli, "cmd_lint", stub):
                    cli.cmd_all(_mk_args(search_mode="tree"))

    build_argv = next((a for a in received_argvs if a and a[0] == "build"), None)
    assert build_argv is not None
    assert "--search-mode" in build_argv
    sm_idx = build_argv.index("--search-mode")
    assert build_argv[sm_idx + 1] == "tree"


def test_cmd_all_runs_all_four_steps_by_default():
    """build → graph → export → lint, in that order."""
    from llmwiki import cli

    order: list[str] = []
    def make_stub(name: str):
        def _stub(_args):
            order.append(name)
            return 0
        return _stub

    with patch.object(cli, "cmd_build", side_effect=make_stub("build")):
        with patch.object(cli, "cmd_graph", side_effect=make_stub("graph")):
            with patch.object(cli, "cmd_export", side_effect=make_stub("export")):
                with patch.object(cli, "cmd_lint", side_effect=make_stub("lint")):
                    cli.cmd_all(_mk_args(skip_graph=False))

    assert order == ["build", "graph", "export", "lint"]
