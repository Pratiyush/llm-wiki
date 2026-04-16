"""Tests for v0.3 additions — eval framework, i18n docs, pyproject."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki import __version__

from tests.conftest import REPO_ROOT


# ─── version bump ────────────────────────────────────────────────────────


def test_version_is_at_least_v03():
    """v0.3 introduced pyproject. Any version >= 0.3 must continue to work."""
    major, minor, *_ = __version__.split(".")
    assert int(major) > 0 or int(minor) >= 3, f"expected >= 0.3, got {__version__}"


# ─── pyproject.toml ──────────────────────────────────────────────────────


def test_pyproject_exists():
    p = REPO_ROOT / "pyproject.toml"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    # Minimal sanity
    assert 'name = "llmwiki"' in content
    # Accept any valid semver — bumped to 1.0 in v1.0.0 release
    import re
    assert re.search(r'version = "\d+\.\d+\.\d+', content), "missing version string"
    assert "markdown" in content
    assert "[project.scripts]" in content


def test_pyproject_declares_optional_deps():
    p = REPO_ROOT / "pyproject.toml"
    content = p.read_text(encoding="utf-8")
    # optional-dependencies section
    assert "[project.optional-dependencies]" in content
    for opt in ("highlight", "pdf", "dev", "all"):
        assert f"{opt} =" in content, f"missing optional dep group: {opt}"


# ─── eval framework ──────────────────────────────────────────────────────


def test_eval_module_imports():
    from llmwiki.eval import (
        run_eval,
        scan_pages,
        parse_frontmatter,
        CHECKS,
        Check,
        OrphanCheck,
        BrokenLinkCheck,
        FrontmatterCheck,
        CoverageCheck,
        CrossLinkingCheck,
        SizeCheck,
        ContradictionCheck,
    )
    assert callable(run_eval)
    assert len(CHECKS) == 7


def test_eval_parse_frontmatter_simple():
    from llmwiki.eval import parse_frontmatter

    fm = parse_frontmatter('---\ntitle: "Hello"\ntype: source\n---\n\nBody text\n')
    assert fm["title"] == "Hello"
    assert fm["type"] == "source"


def test_eval_parse_frontmatter_no_frontmatter():
    from llmwiki.eval import parse_frontmatter

    fm = parse_frontmatter("# Just a heading\n")
    assert fm == {}


def test_eval_scan_pages_returns_dict():
    from llmwiki.eval import scan_pages

    pages = scan_pages()
    assert isinstance(pages, dict)
    # Each page should have the expected keys
    for slug, page in pages.items():
        for key in ("path", "type", "frontmatter", "body", "size", "out_links"):
            assert key in page, f"{slug} missing {key}"


def test_eval_run_produces_report():
    from llmwiki.eval import run_eval

    report = run_eval()
    for key in ("total_score", "total_max", "percentage", "total_pages", "checks"):
        assert key in report, f"missing {key} in eval report"
    assert isinstance(report["checks"], list)
    assert len(report["checks"]) == 7


def test_eval_individual_checks_score_within_max():
    from llmwiki.eval import CHECKS, scan_pages

    pages = scan_pages()
    for cls in CHECKS:
        check = cls()
        result = check.run(pages)
        score = result.get("score", 0)
        max_ = result.get("max", cls.max_score)
        assert 0 <= score <= max_, f"{cls.name}: score {score} out of range 0..{max_}"


def test_eval_selective_check_runs_only_requested():
    from llmwiki.eval import run_eval

    report = run_eval(selected=["orphans"])
    assert len(report["checks"]) == 1
    assert report["checks"][0]["name"] == "orphans"


# ─── i18n docs ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("lang", ["es", "zh-CN", "ja"])
def test_i18n_getting_started_exists(lang: str):
    p = REPO_ROOT / "docs" / "i18n" / lang / "getting-started.md"
    assert p.exists(), f"missing {lang} translation of getting-started.md"
    content = p.read_text(encoding="utf-8")
    # Each translation should link back to the English master
    assert "docs/getting-started.md" in content or "../../getting-started.md" in content


def test_i18n_readme_lists_all_languages():
    p = REPO_ROOT / "docs" / "i18n" / "README.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    for lang in ("es", "zh-CN", "ja"):
        assert lang in content, f"i18n README doesn't list {lang}"


# ─── CLI subcommand ──────────────────────────────────────────────────────


def test_cli_has_eval_subcommand():
    from llmwiki.cli import build_parser

    parser = build_parser()
    help_text = parser.format_help()
    assert "eval" in help_text
