"""Tests for the first-class /changelog page (#72).

``llmwiki.build.render_changelog`` reads ``CHANGELOG.md`` at the repo root and
renders it to ``site/changelog.html``. These tests pin the contract so a
future refactor doesn't silently drop the page or mangle its layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.build import render_changelog


@pytest.fixture
def tmp_out(tmp_path: Path) -> Path:
    out = tmp_path / "site"
    out.mkdir()
    return out


def test_render_changelog_writes_file(tmp_out: Path):
    out = render_changelog(tmp_out)
    assert out is not None
    assert out.exists()
    assert out.name == "changelog.html"


def test_render_changelog_contains_hero_and_nav(tmp_out: Path):
    render_changelog(tmp_out)
    html = (tmp_out / "changelog.html").read_text(encoding="utf-8")
    # Hero
    assert "Changelog" in html
    # Nav link is marked active
    assert 'class="active"' in html
    # No duplicate top-level "# Changelog" H1 inside article (we strip it
    # so the hero owns the title).
    assert html.count("<h1>Changelog</h1>") == 1


def test_render_changelog_renders_markdown_headings(tmp_out: Path):
    render_changelog(tmp_out)
    html = (tmp_out / "changelog.html").read_text(encoding="utf-8")
    # Keep-a-changelog headings come through as <h2>
    assert "[Unreleased]" in html or "Unreleased" in html
    assert "<h2" in html


def test_render_changelog_returns_none_when_missing(tmp_path: Path, monkeypatch):
    # Point REPO_ROOT at an empty tmp dir so CHANGELOG.md is missing.
    import llmwiki.build as build

    empty = tmp_path / "empty_repo"
    empty.mkdir()
    monkeypatch.setattr(build, "REPO_ROOT", empty)
    out_dir = tmp_path / "site"
    out_dir.mkdir()
    assert render_changelog(out_dir) is None
    assert not (out_dir / "changelog.html").exists()


def test_render_changelog_is_well_formed_html(tmp_out: Path):
    render_changelog(tmp_out)
    html = (tmp_out / "changelog.html").read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert html.rstrip().endswith("</html>")
    # Narrow reading column class applied so the changelog doesn't span
    # the full 1080px content width.
    assert "container narrow" in html
