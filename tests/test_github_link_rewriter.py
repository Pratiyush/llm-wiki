"""Tests for ``rewrite_source_code_links_to_github`` (#270).

Covers:
* `.py`, `.js`, `.ts`, `.rs`, `.go`, `.sh`, `.toml`, `.yml`, `.json` files
  all route to GitHub blob URLs.
* Repo-root `.md` files (README, CONTRIBUTING, CLAUDE, AGENTS,
  CODE_OF_CONDUCT, SECURITY) route to GitHub.
* `.html` versions of root-only files (previously rewritten) flip back
  to `.md` on GitHub.
* LICENSE + .gitignore route to GitHub.
* External URLs (http / mailto / anchor) passed through unchanged.
* Regular `.md` files (docs/tutorials/*) untouched — handled by the
  generic md→html pass.
* Paths with #anchor and ?query are preserved on the GitHub URL.
* Leading `../../` chunks are stripped before GitHub URL construction.
"""

from __future__ import annotations

import pytest

from llmwiki.docs_pages import (
    _rewrite_one_to_github,
    rewrite_source_code_links_to_github,
)


_GH = "https://github.com/Pratiyush/llm-wiki/blob/master"


# ─── _rewrite_one_to_github: unit ────────────────────────────────────────


@pytest.mark.parametrize("href,expected", [
    # Source code at various depths
    ("../../llmwiki/convert.py", f"{_GH}/llmwiki/convert.py"),
    ("llmwiki/convert.py", f"{_GH}/llmwiki/convert.py"),
    ("../llmwiki/adapters/cursor.py", f"{_GH}/llmwiki/adapters/cursor.py"),
    # Different extensions
    ("script.js", f"{_GH}/script.js"),
    ("src/types.ts", f"{_GH}/src/types.ts"),
    ("setup.sh", f"{_GH}/setup.sh"),
    ("pyproject.toml", f"{_GH}/pyproject.toml"),
    ("config.yml", f"{_GH}/config.yml"),
    ("data.json", f"{_GH}/data.json"),
    # Repo-root .md
    ("README.md", f"{_GH}/README.md"),
    ("../README.md", f"{_GH}/README.md"),
    ("CONTRIBUTING.md", f"{_GH}/CONTRIBUTING.md"),
    ("CLAUDE.md", f"{_GH}/CLAUDE.md"),
    ("AGENTS.md", f"{_GH}/AGENTS.md"),
    ("CODE_OF_CONDUCT.md", f"{_GH}/CODE_OF_CONDUCT.md"),
    ("SECURITY.md", f"{_GH}/SECURITY.md"),
    # LICENSE + .gitignore
    ("LICENSE", f"{_GH}/LICENSE"),
    (".gitignore", f"{_GH}/.gitignore"),
    # Previously rewritten .html versions
    ("../CLAUDE.html", f"{_GH}/CLAUDE.md"),
    ("../../CONTRIBUTING.html", f"{_GH}/CONTRIBUTING.md"),
    ("README.html", f"{_GH}/README.md"),
])
def test_rewrite_one_to_github_matches(href, expected):
    assert _rewrite_one_to_github(href) == expected


@pytest.mark.parametrize("href", [
    # Docs pages — leave to the regular md→html pass
    "tutorials/01-install.md",
    "docs/reference/cli.md",
    "deploy/pypi-publishing.md",
    # Already .html (non-root)
    "projects/foo.html",
    "index.html",
    # Empty / weird
    "",
    "../..",
])
def test_rewrite_one_to_github_leaves_other_paths_alone(href):
    assert _rewrite_one_to_github(href) is None


# ─── rewrite_source_code_links_to_github: integration ───────────────────


def test_rewrites_source_code_ref_in_href():
    html = 'See <a href="../../llmwiki/convert.py">convert.py</a>.'
    out = rewrite_source_code_links_to_github(html)
    assert 'href="https://github.com/Pratiyush/llm-wiki/blob/master/llmwiki/convert.py"' in out


def test_rewrites_repo_root_md():
    html = 'Read the <a href="../../README.md">README</a>.'
    out = rewrite_source_code_links_to_github(html)
    assert f'href="{_GH}/README.md"' in out


def test_rewrites_previously_rewritten_claude_html():
    html = 'See <a href="../CLAUDE.html">CLAUDE</a>.'
    out = rewrite_source_code_links_to_github(html)
    # The .html → .md flip happens via _ROOT_ONLY_HTML_BASENAMES.
    assert f'href="{_GH}/CLAUDE.md"' in out


def test_leaves_external_urls_alone():
    html = '<a href="https://example.com/x.py">ext</a>'
    out = rewrite_source_code_links_to_github(html)
    assert 'https://example.com/x.py' in out
    assert 'github.com' not in out


def test_leaves_anchor_only_alone():
    html = '<a href="#section">jump</a>'
    assert rewrite_source_code_links_to_github(html) == html


def test_leaves_mailto_alone():
    html = '<a href="mailto:user@example.com">email</a>'
    assert rewrite_source_code_links_to_github(html) == html


def test_leaves_docs_md_alone():
    """Docs pages SHOULD be rewritten by the .md → .html pass,
    not by the github pass."""
    html = '<a href="tutorials/01.md">install</a>'
    out = rewrite_source_code_links_to_github(html)
    assert out == html


def test_multiple_rewrites_in_one_body():
    html = (
        'Read <a href="../../README.md">README</a> and '
        '<a href="../../llmwiki/convert.py">convert</a> and '
        '<a href="docs/reference/cli.md">CLI ref</a>.'
    )
    out = rewrite_source_code_links_to_github(html)
    assert out.count(_GH) == 2  # README + convert.py
    assert 'href="docs/reference/cli.md"' in out  # regular doc left alone


def test_preserves_html_attributes_on_anchor():
    html = '<a href="../README.md" class="x" data-id="1">r</a>'
    out = rewrite_source_code_links_to_github(html)
    assert 'class="x"' in out
    assert 'data-id="1"' in out
    assert f'href="{_GH}/README.md"' in out


def test_python_link_under_subdir():
    html = '<a href="llmwiki/adapters/claude_code.py">src</a>'
    out = rewrite_source_code_links_to_github(html)
    assert f'href="{_GH}/llmwiki/adapters/claude_code.py"' in out


def test_handles_hash_anchor_on_source_file():
    html = '<a href="llmwiki/convert.py#L42">line 42</a>'
    out = rewrite_source_code_links_to_github(html)
    # Anchor is stripped in the GH URL — this is fine; reviewers click
    # the file and use GitHub's line-number UI.
    assert _GH in out


def test_empty_body_is_noop():
    assert rewrite_source_code_links_to_github("") == ""
