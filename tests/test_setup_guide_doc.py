"""Tests for the end-to-end setup guide tutorial (v1.0, #120)."""

from __future__ import annotations

import pytest

from llmwiki import REPO_ROOT


GUIDE = REPO_ROOT / "docs" / "tutorials" / "setup-guide.md"


def test_guide_exists():
    assert GUIDE.is_file()


def test_guide_has_5_parts():
    text = GUIDE.read_text(encoding="utf-8")
    for n in range(1, 6):
        assert f"## Part {n}:" in text, f"missing Part {n}"


def test_part1_has_core_steps():
    text = GUIDE.read_text(encoding="utf-8")
    assert "git clone" in text
    assert "setup.sh" in text
    assert "setup.bat" in text
    assert "llmwiki sync" in text
    assert "llmwiki build" in text
    assert "llmwiki serve" in text


def test_part2_explains_three_layers():
    text = GUIDE.read_text(encoding="utf-8")
    assert "raw/" in text
    assert "wiki/" in text
    assert "site/" in text


def test_part3_covers_github_pages():
    text = GUIDE.read_text(encoding="utf-8")
    assert "GitHub Pages" in text
    assert "pages.yml" in text
    assert "Settings → Pages" in text or "Settings -> Pages" in text


def test_part4_covers_customization():
    text = GUIDE.read_text(encoding="utf-8")
    assert "wiki/projects/" in text
    assert "wiki/entities/" in text
    assert "link-obsidian" in text


def test_part5_covers_multi_agent():
    text = GUIDE.read_text(encoding="utf-8")
    # `install-skills` CLI was removed in v1.2.0 (#362); guide now shows
    # the manual copy of `.claude/commands/` files. Section 5.2 must
    # still cover the multi-agent share story.
    assert ".claude/commands/" in text
    assert "Claude Code" in text
    assert "Codex" in text


def test_guide_links_to_other_docs():
    text = GUIDE.read_text(encoding="utf-8")
    assert "obsidian-integration.md" in text
    assert "architecture.md" in text
    assert "configuration.md" in text


def test_guide_uses_images():
    text = GUIDE.read_text(encoding="utf-8")
    # References screenshots in docs/images/
    assert "../images/home.png" in text
    assert "../images/session-detail.png" in text


def test_readme_links_to_guide():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/tutorials/setup-guide.md" in readme


def test_guide_mentions_privacy_boundary():
    """Must explain that raw/wiki are gitignored and personal data stays local."""
    text = GUIDE.read_text(encoding="utf-8")
    assert "gitignored" in text.lower() or "never your personal data" in text.lower()


def test_guide_shows_new_v1_cli_commands():
    """The guide must mention the canonical v1.2 CLI surface. `link-obsidian`
    + `install-skills` were removed in v1.2.0 (#362); `all` is the new
    one-shot command users should know about."""
    text = GUIDE.read_text(encoding="utf-8")
    for cmd in ["llmwiki adapters"]:
        assert cmd in text, f"missing {cmd}"
