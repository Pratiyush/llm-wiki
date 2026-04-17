"""Tests for the PR template (post-v1.0 governance upgrade)."""

from __future__ import annotations

import pytest

from llmwiki import REPO_ROOT


TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"


# ─── PR template ──────────────────────────────────────────────────────


def test_template_exists():
    assert TEMPLATE.is_file()


def test_template_has_summary_section():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "## Summary" in text


def test_template_has_closes_hint():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Closes #" in text


def test_template_has_how_to_test():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "How to test" in text


def test_template_has_pre_merge_checklist():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Pre-merge checklist" in text


def test_template_checklist_enforces_one_intent():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "One intent" in text


def test_template_checklist_enforces_conventional_commit_title():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Conventional-commit title" in text


def test_template_checklist_enforces_changelog_update():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "CHANGELOG.md updated" in text


def test_template_checklist_flags_breaking_changes():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Breaking changes" in text


def test_template_checklist_blocks_new_runtime_deps():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "No new runtime dependencies" in text


def test_template_checklist_protects_privacy():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "No real session data" in text
    assert "No machine-specific paths" in text


def test_template_checklist_requires_ui_verification_light_and_dark():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "light AND dark" in text


def test_template_checklist_requires_a11y():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "A11y verified" in text
    assert "WCAG" in text


def test_template_checklist_requires_gpg_signed():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "GPG-signed" in text
    # Match exact template wording "no AI co-author trailers"
    assert "no AI co-author trailers" in text


def test_template_checklist_requires_reviewer_reads_lines():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "read every changed line" in text


def test_template_has_screenshots_section():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Screenshots / output" in text


def test_template_has_out_of_scope_section():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Out of scope" in text


# ─── CONTRIBUTING.md matches template ────────────────────────────────


def test_contributing_documents_15_box_checklist():
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert "15-box pre-merge checklist" in text


def test_contributing_lists_all_conventional_commit_types():
    text = CONTRIBUTING.read_text(encoding="utf-8")
    for t in ["feat", "fix", "chore", "docs", "test", "refactor",
              "perf", "security", "release"]:
        assert f"`{t}`" in text, f"missing commit type: {t}"


def test_contributing_enforces_500_line_limit():
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert "500 lines" in text


def test_contributing_requires_signed_commits_branch_protection():
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert "Signed commits required" in text
