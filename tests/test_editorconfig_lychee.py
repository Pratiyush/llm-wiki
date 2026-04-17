"""Tests for .editorconfig + lychee link checker (v1.1.0, #215)."""

from __future__ import annotations

import re

import pytest

from llmwiki import REPO_ROOT


EDITORCONFIG = REPO_ROOT / ".editorconfig"
LYCHEE = REPO_ROOT / "lychee.toml"
LINK_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "link-check.yml"


# ─── .editorconfig ────────────────────────────────────────────────────


def test_editorconfig_exists():
    assert EDITORCONFIG.is_file()


def test_editorconfig_is_root():
    text = EDITORCONFIG.read_text(encoding="utf-8")
    assert "root = true" in text


def test_editorconfig_default_rules():
    text = EDITORCONFIG.read_text(encoding="utf-8")
    assert "charset = utf-8" in text
    assert "end_of_line = lf" in text
    assert "insert_final_newline = true" in text


def test_editorconfig_python_has_4_space_indent():
    text = EDITORCONFIG.read_text(encoding="utf-8")
    # Python block has indent_size = 4
    py_block = re.search(r"\[\*\.py\](.*?)(\[|\Z)", text, re.DOTALL)
    assert py_block is not None
    assert "indent_size = 4" in py_block.group(1)


def test_editorconfig_yaml_json_has_2_space_indent():
    text = EDITORCONFIG.read_text(encoding="utf-8")
    # Check YAML/JSON block has 2-space
    yaml_block = re.search(r"\[\*\.\{yml,yaml,json,toml\}\](.*?)(\[|\Z)", text, re.DOTALL)
    assert yaml_block is not None
    assert "indent_size = 2" in yaml_block.group(1)


def test_editorconfig_makefile_uses_tabs():
    text = EDITORCONFIG.read_text(encoding="utf-8")
    mk_block = re.search(r"\[\{Makefile,\*\.mk\}\](.*?)(\[|\Z)", text, re.DOTALL)
    assert mk_block is not None
    assert "indent_style = tab" in mk_block.group(1)


def test_editorconfig_windows_batch_uses_crlf():
    text = EDITORCONFIG.read_text(encoding="utf-8")
    assert re.search(r"\[\*\.\{bat,cmd\}\][\s\S]*?end_of_line = crlf", text)


# ─── lychee.toml ──────────────────────────────────────────────────────


def test_lychee_config_exists():
    assert LYCHEE.is_file()


def test_lychee_has_sensible_timeouts():
    text = LYCHEE.read_text(encoding="utf-8")
    assert re.search(r"^timeout\s*=\s*\d+", text, re.MULTILINE)
    assert re.search(r"^max_retries\s*=\s*\d+", text, re.MULTILINE)


def test_lychee_excludes_built_site():
    text = LYCHEE.read_text(encoding="utf-8")
    assert '"site/"' in text


def test_lychee_excludes_user_data_folders():
    text = LYCHEE.read_text(encoding="utf-8")
    # Personal raw/ + wiki/ folders must not be scanned
    assert '"wiki/"' in text
    assert '"raw/"' in text


def test_lychee_excludes_unpublished_drafts():
    text = LYCHEE.read_text(encoding="utf-8")
    assert '"docs/content-drafts/"' in text


def test_lychee_skips_known_future_urls():
    text = LYCHEE.read_text(encoding="utf-8")
    # Release tags for v1.1 / v1.2 may not exist yet
    assert "v1\\\\.1" in text or "v1.1" in text


def test_lychee_skips_pypi_and_homebrew_placeholders():
    text = LYCHEE.read_text(encoding="utf-8")
    assert "pypi" in text
    assert "homebrew-llmwiki" in text


# ─── workflow ─────────────────────────────────────────────────────────


def test_link_check_workflow_exists():
    assert LINK_WORKFLOW.is_file()


def test_workflow_runs_weekly():
    text = LINK_WORKFLOW.read_text(encoding="utf-8")
    assert "cron:" in text
    # "0 3 * * 0" = Sunday 03:00 UTC
    assert re.search(r'cron:\s*"[0-9\s*]+"', text)


def test_workflow_allows_manual_dispatch():
    text = LINK_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch" in text


def test_workflow_uses_lychee_action():
    text = LINK_WORKFLOW.read_text(encoding="utf-8")
    assert "lycheeverse/lychee-action" in text


def test_workflow_uses_cache():
    text = LINK_WORKFLOW.read_text(encoding="utf-8")
    assert "actions/cache" in text
    assert ".lycheecache" in text


def test_workflow_files_issue_on_broken_links():
    text = LINK_WORKFLOW.read_text(encoding="utf-8")
    assert "create-issue-from-file" in text


def test_workflow_scans_required_paths():
    text = LINK_WORKFLOW.read_text(encoding="utf-8")
    for path in ["README.md", "CHANGELOG.md", "docs/**/*.md", "examples/**/*.md"]:
        assert path in text, f"missing scan path: {path}"


def test_workflow_uses_pinned_action_versions():
    text = LINK_WORKFLOW.read_text(encoding="utf-8")
    # actions/checkout@v4 (pinned in the dependency bundle PR #189)
    assert "actions/checkout@v4" in text
