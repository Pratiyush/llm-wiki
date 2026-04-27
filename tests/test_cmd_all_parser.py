"""Tests for the `llmwiki all` orchestrator (closes #422 and #583).

#422: `cmd_all` was calling `build_parser()` once *per step* (4× per
invocation). Wasteful argparse work AND a coupling smell.

#py-h4 (#583): `cmd_all` then re-parsed argv lists via the global
parser — semantically correct but the global parser still leaked into
`cmd_all`'s contract. Rewritten to direct-dispatch: each step gets a
Namespace constructed in-place with the defaults that subcommand
expects, and we call `cmd_build` / `cmd_graph` / `cmd_export` /
`cmd_lint` directly. No global parser involvement.
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


def test_cmd_all_does_not_use_global_parser():
    """#py-h4 (#583): cmd_all must NOT call build_parser() at all.

    Previously: 4× (#422 era), then 1× (post-#422). Now: 0× — direct
    dispatch via cmd_* function references. Calling build_parser inside
    cmd_all means the global parser's grammar leaks into cmd_all's
    contract; adding a flag to any unrelated subcommand could regress
    cmd_all if defaults shifted.
    """
    from llmwiki import cli

    call_count = {"n": 0}
    original_build_parser = cli.build_parser

    def counting_build_parser():
        call_count["n"] += 1
        return original_build_parser()

    stub = MagicMock(return_value=0)
    with patch.object(cli, "build_parser", side_effect=counting_build_parser):
        with patch.object(cli, "cmd_build", stub):
            with patch.object(cli, "cmd_lint", stub):
                with patch.object(cli, "cmd_export", stub):
                    cli.cmd_all(_mk_args())

    assert call_count["n"] == 0, (
        f"cmd_all called build_parser() {call_count['n']} times "
        f"(expected 0 — see #583)"
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


def test_cmd_all_strict_propagates_fail_on_errors_to_lint():
    """#py-h4 (#583): --strict sets fail_on_errors=True on the lint step."""
    from llmwiki import cli

    lint_stub = MagicMock(return_value=0)
    other = MagicMock(return_value=0)
    with patch.object(cli, "cmd_build", other):
        with patch.object(cli, "cmd_export", other):
            with patch.object(cli, "cmd_lint", lint_stub):
                cli.cmd_all(_mk_args(strict=True))

    assert lint_stub.call_count == 1
    lint_ns = lint_stub.call_args[0][0]
    assert lint_ns.fail_on_errors is True


def test_cmd_all_strict_false_keeps_lint_permissive():
    """Without --strict, lint runs without fail_on_errors."""
    from llmwiki import cli

    lint_stub = MagicMock(return_value=0)
    other = MagicMock(return_value=0)
    with patch.object(cli, "cmd_build", other):
        with patch.object(cli, "cmd_export", other):
            with patch.object(cli, "cmd_lint", lint_stub):
                cli.cmd_all(_mk_args(strict=False))

    lint_ns = lint_stub.call_args[0][0]
    assert lint_ns.fail_on_errors is False


def test_cmd_all_out_dir_propagates_to_build_and_export():
    """#py-h4 (#583): --out flows through to both build and export Namespaces."""
    from llmwiki import cli

    build_stub = MagicMock(return_value=0)
    export_stub = MagicMock(return_value=0)
    with patch.object(cli, "cmd_build", build_stub):
        with patch.object(cli, "cmd_export", export_stub):
            with patch.object(cli, "cmd_lint", MagicMock(return_value=0)):
                cli.cmd_all(_mk_args(out=Path("/custom/out")))

    assert build_stub.call_args[0][0].out == Path("/custom/out")
    assert export_stub.call_args[0][0].out == Path("/custom/out")


def test_cmd_all_search_mode_propagates_to_build():
    """#py-h4 (#583): --search-mode flows through to build's Namespace."""
    from llmwiki import cli

    build_stub = MagicMock(return_value=0)
    other = MagicMock(return_value=0)
    with patch.object(cli, "cmd_build", build_stub):
        with patch.object(cli, "cmd_export", other):
            with patch.object(cli, "cmd_lint", other):
                cli.cmd_all(_mk_args(search_mode="tree"))

    assert build_stub.call_args[0][0].search_mode == "tree"


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
