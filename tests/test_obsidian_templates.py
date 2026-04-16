"""Tests for Obsidian Templater templates (v1.0, #152)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki import REPO_ROOT


TEMPLATES_DIR = REPO_ROOT / "examples" / "obsidian-templates"


def test_templates_dir_exists():
    assert TEMPLATES_DIR.is_dir()


def test_readme_exists():
    assert (TEMPLATES_DIR / "README.md").is_file()


@pytest.mark.parametrize("name", [
    "source-template.md",
    "entity-template.md",
    "concept-template.md",
    "synthesis-template.md",
])
def test_template_file_exists(name):
    assert (TEMPLATES_DIR / name).is_file()


def test_source_template_has_required_fields():
    text = (TEMPLATES_DIR / "source-template.md").read_text(encoding="utf-8")
    for field in ["type: source", "tags:", "date:", "source_file:",
                  "project:", "confidence:", "lifecycle:", "last_updated:"]:
        assert field in text, f"missing frontmatter field: {field}"


def test_entity_template_has_entity_type():
    text = (TEMPLATES_DIR / "entity-template.md").read_text(encoding="utf-8")
    assert "entity_type:" in text
    # Templater prompts for one of the 7 valid types
    for etype in ["person", "org", "tool", "concept", "api", "library", "project"]:
        assert etype in text


def test_entity_template_has_inline_dataview():
    text = (TEMPLATES_DIR / "entity-template.md").read_text(encoding="utf-8")
    assert "```dataview" in text


def test_concept_template_has_inline_dataview():
    text = (TEMPLATES_DIR / "concept-template.md").read_text(encoding="utf-8")
    assert "```dataview" in text


def test_synthesis_template_has_question_section():
    text = (TEMPLATES_DIR / "synthesis-template.md").read_text(encoding="utf-8")
    assert "## Question" in text
    assert "## Answer" in text


@pytest.mark.parametrize("name", [
    "source-template.md",
    "entity-template.md",
    "concept-template.md",
    "synthesis-template.md",
])
def test_templates_have_connections_section(name):
    text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    assert "## Connections" in text


@pytest.mark.parametrize("name", [
    "source-template.md",
    "entity-template.md",
    "concept-template.md",
    "synthesis-template.md",
])
def test_templates_use_templater_syntax(name):
    text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    # Templater tags
    assert "<%" in text and "%>" in text


@pytest.mark.parametrize("name", [
    "source-template.md",
    "entity-template.md",
    "concept-template.md",
    "synthesis-template.md",
])
def test_templates_seed_lifecycle_draft(name):
    text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    # Synthesis is the one exception — doesn't need lifecycle
    if "synthesis" not in name:
        assert "lifecycle: draft" in text


@pytest.mark.parametrize("name", [
    "source-template.md",
    "entity-template.md",
    "concept-template.md",
])
def test_templates_seed_confidence(name):
    text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    assert "confidence:" in text


def test_readme_lists_all_templates():
    text = (TEMPLATES_DIR / "README.md").read_text(encoding="utf-8")
    for name in ["source-template.md", "entity-template.md",
                 "concept-template.md", "synthesis-template.md"]:
        assert name in text


def test_readme_mentions_templater_plugin():
    text = (TEMPLATES_DIR / "README.md").read_text(encoding="utf-8")
    assert "Templater" in text
