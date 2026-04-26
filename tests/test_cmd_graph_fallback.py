"""Tests for #488 — cmd_graph must always fall back to the builtin
engine when the graphify path fails.

Two missing fallbacks in the original code:
  1. Uncaught exception from build_graphify_graph() propagated as
     a stack trace + non-zero exit.
  2. result.get("graph") is None returned 1 directly without trying
     builtin (legitimate empty-corpus case).
"""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest

from llmwiki.cli import cmd_graph


def _make_args(engine="graphify", fmt="both"):
    return argparse.Namespace(engine=engine, format=fmt)


def test_graphify_exception_falls_back_to_builtin(monkeypatch, capsys):
    """graphify crashing must log + fall through, not propagate."""
    with patch("llmwiki.graphify_bridge.is_available", return_value=True), \
         patch("llmwiki.graphify_bridge.build_graphify_graph",
               side_effect=RuntimeError("graphify exploded")), \
         patch("llmwiki.graph.build_and_report", return_value=0) as builtin:
        rc = cmd_graph(_make_args())
    assert rc == 0
    builtin.assert_called_once()
    err = capsys.readouterr().err
    assert "graphify engine crashed" in err
    assert "falling back to builtin" in err


def test_graphify_empty_result_falls_back_to_builtin(monkeypatch, capsys):
    """When graphify returns {graph: None} (e.g. tiny corpus with no
    edges), fall through instead of returning 1."""
    with patch("llmwiki.graphify_bridge.is_available", return_value=True), \
         patch("llmwiki.graphify_bridge.build_graphify_graph",
               return_value={"graph": None}), \
         patch("llmwiki.graph.build_and_report", return_value=0) as builtin:
        rc = cmd_graph(_make_args())
    assert rc == 0
    builtin.assert_called_once()
    err = capsys.readouterr().err
    assert "no graph" in err.lower() or "falling back" in err.lower()


def test_graphify_success_short_circuits(monkeypatch):
    """When graphify produces a real graph, builtin is NOT called."""
    with patch("llmwiki.graphify_bridge.is_available", return_value=True), \
         patch("llmwiki.graphify_bridge.build_graphify_graph",
               return_value={"graph": {"nodes": [{"id": "x"}], "edges": []}}), \
         patch("llmwiki.graph.build_and_report") as builtin:
        rc = cmd_graph(_make_args())
    assert rc == 0
    builtin.assert_not_called()


def test_graphify_unavailable_falls_back_to_builtin(monkeypatch, capsys):
    """When graphify isn't installed, fall through cleanly (no crash)."""
    with patch("llmwiki.graphify_bridge.is_available", return_value=False), \
         patch("llmwiki.graph.build_and_report", return_value=0) as builtin:
        rc = cmd_graph(_make_args())
    assert rc == 0
    builtin.assert_called_once()
    err = capsys.readouterr().err
    assert "graphify not installed" in err
