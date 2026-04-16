"""Tests for the Dataview dashboard template (v1.0, #153)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki import REPO_ROOT


DASHBOARD_TEMPLATE = REPO_ROOT / "examples" / "wiki_dashboard.md"


def test_dashboard_template_exists():
    assert DASHBOARD_TEMPLATE.is_file()


def test_dashboard_has_frontmatter():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert 'type: navigation' in text


def test_dashboard_has_recently_updated():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "Recently Updated" in text


def test_dashboard_has_confidence_sections():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "High confidence" in text
    assert "Low confidence" in text


def test_dashboard_has_all_lifecycle_states():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    for state in ["Draft", "Reviewed", "Verified", "Stale", "Archived"]:
        assert state in text, f"missing lifecycle section: {state}"


def test_dashboard_has_by_project():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "By Project" in text


def test_dashboard_has_entity_type_breakdown():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "entity_type" in text


def test_dashboard_has_open_questions():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "Open Questions" in text


def test_dashboard_has_dataview_blocks():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    # At least 8 dataview code blocks expected
    count = text.count("```dataview")
    assert count >= 8


def test_dashboard_has_connections_section():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "## Connections" in text


def test_cmd_init_seeds_dashboard(tmp_path: Path, monkeypatch):
    """cmd_init should copy the dashboard template to wiki/dashboard.md."""
    monkeypatch.setattr("llmwiki.cli.REPO_ROOT", tmp_path)
    # Copy the template into the tmp REPO_ROOT
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "wiki_dashboard.md").write_text(
        "---\ntitle: Test\n---\n# Test Dashboard\n", encoding="utf-8"
    )

    import argparse
    from llmwiki.cli import cmd_init
    args = argparse.Namespace()
    rc = cmd_init(args)
    assert rc == 0
    dashboard = tmp_path / "wiki" / "dashboard.md"
    assert dashboard.is_file()
    assert "Test Dashboard" in dashboard.read_text(encoding="utf-8")
