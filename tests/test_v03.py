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
    # Distribution name is `llm-notebook` (the `llmwiki` name was taken on
    # PyPI). Python module + CLI command remain `llmwiki`.
    assert 'name = "llm-notebook"' in content
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
    # `pdf` extra was removed in the simplification sweep alongside the
    # PDF adapter. The remaining optional groups must stay declared.
    for opt in ("highlight", "dev", "all"):
        assert f"{opt} =" in content, f"missing optional dep group: {opt}"
    assert "pdf =" not in content, (
        "pdf optional dep was removed in the simplification sweep; "
        "don't reintroduce it"
    )


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


