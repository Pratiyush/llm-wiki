"""Tests for the Obsidian integration documentation (v1.0, #151)."""

from __future__ import annotations

import pytest

from llmwiki import REPO_ROOT


DOC = REPO_ROOT / "docs" / "obsidian-integration.md"


def test_doc_exists():
    assert DOC.is_file()


def test_doc_has_setup_section():
    text = DOC.read_text(encoding="utf-8")
    assert "## Setup" in text


def test_doc_covers_link_obsidian_command():
    text = DOC.read_text(encoding="utf-8")
    assert "link-obsidian" in text


def test_doc_covers_all_core_plugins():
    text = DOC.read_text(encoding="utf-8")
    for plugin in ["Dataview", "Templater", "Obsidian Linter", "Web Clipper"]:
        assert plugin in text, f"missing plugin: {plugin}"


def test_doc_has_plugin_config_section():
    text = DOC.read_text(encoding="utf-8")
    assert "## Plugin Configuration" in text


def test_doc_has_workflow_section():
    text = DOC.read_text(encoding="utf-8")
    assert "## Workflow" in text


def test_doc_has_two_way_editing_note():
    text = DOC.read_text(encoding="utf-8")
    assert "Two-way editing" in text


def test_doc_links_to_related_files():
    text = DOC.read_text(encoding="utf-8")
    # References to other docs/templates
    assert "CLAUDE.md" in text
    assert "wiki_dashboard.md" in text
