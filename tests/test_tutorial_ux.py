"""Tests for tutorial UX polish (#282).

Covers:
* ``_tutorial_seq`` sorts numbered pages by their two-digit prefix.
* ``_tutorial_toc_html`` returns empty for pages with <2 headings.
* ``_tutorial_toc_html`` emits one list-item per ## / ### heading
  with slug anchors.
* ``_tutorial_footer_html`` returns prev/next + edit-on-GitHub links
  for every numbered tutorial; first tutorial has no prev, last no
  next.
* ``compile_docs_site`` injects the footer on every tutorial and
  the TOC on pages with ≥2 headings.
* Passthrough (non-tutorial) pages don't get TOC or footer.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from llmwiki.docs_pages import (
    DocsPage,
    _tutorial_footer_html,
    _tutorial_seq,
    _tutorial_toc_html,
    compile_docs_site,
)


# ─── _tutorial_seq ────────────────────────────────────────────────────


def _page(rel: str, title: str = "T", body: str = "body"):
    return DocsPage(
        source=Path(rel),
        rel=rel,
        title=title,
        meta={},
        body=body,
        is_shell=True,
    )


def test_tutorial_seq_filters_and_sorts():
    pages = [
        _page("tutorials/02-first-sync.md"),
        _page("tutorials/01-installation.md"),
        _page("reference/cli.md"),  # not a tutorial
        _page("tutorials/10-late.md"),
        _page("tutorials/no-number.md"),  # skipped
    ]
    out = _tutorial_seq(pages)
    assert [p.rel for p in out] == [
        "tutorials/01-installation.md",
        "tutorials/02-first-sync.md",
        "tutorials/10-late.md",
    ]


def test_tutorial_seq_empty_when_no_tutorials():
    assert _tutorial_seq([_page("reference/cli.md")]) == []


# ─── _tutorial_toc_html ──────────────────────────────────────────────


def test_toc_empty_when_fewer_than_two_headings():
    assert _tutorial_toc_html("# Only h1\n\nBody.\n") == ""
    assert _tutorial_toc_html("# H1\n\n## Only one H2\n") == ""


def test_toc_emits_entries_for_h2_and_h3():
    body = "# Title\n\n## Alpha\n\n### Bravo\n\n## Charlie\n"
    toc = _tutorial_toc_html(body)
    assert '<nav class="tutorial-toc"' in toc
    assert 'href="#alpha"' in toc
    assert 'href="#bravo"' in toc
    assert 'href="#charlie"' in toc


def test_toc_strips_markdown_emphasis_in_titles():
    body = "## Hello `world`\n\n## **Bold** heading\n"
    toc = _tutorial_toc_html(body)
    # Emphasis markers stripped from visible text but slug is slug-case.
    assert ">Hello world<" in toc
    assert ">Bold heading<" in toc


def test_toc_slugifies_special_characters():
    body = "## A & B (c/d)\n\n## Hello, world!\n"
    toc = _tutorial_toc_html(body)
    # Non-alphanumerics collapse to single hyphens.
    assert 'href="#a-b-c-d"' in toc
    assert 'href="#hello-world"' in toc


# ─── _tutorial_footer_html ───────────────────────────────────────────


def _tutorial_page(num: int, title: str):
    return DocsPage(
        source=Path(f"tutorials/{num:02d}-x.md"),
        rel=f"tutorials/{num:02d}-x.md",
        title=title,
        meta={},
        body="",
        is_shell=True,
    )


def test_footer_first_has_no_prev_but_has_next():
    pages = [_tutorial_page(i, f"T{i}") for i in range(1, 4)]
    html = _tutorial_footer_html(pages[0], pages, "../")
    # first → placeholder for prev
    assert 'class="prev-tut placeholder"' in html
    # next points at 02
    assert 'tutorials/02-x.html' in html
    assert "T2" in html


def test_footer_last_has_no_next_but_has_prev():
    pages = [_tutorial_page(i, f"T{i}") for i in range(1, 4)]
    html = _tutorial_footer_html(pages[-1], pages, "../")
    assert 'class="next-tut placeholder"' in html
    assert 'tutorials/02-x.html' in html  # prev = tutorial 2


def test_footer_middle_has_both_prev_and_next():
    pages = [_tutorial_page(i, f"T{i}") for i in range(1, 4)]
    html = _tutorial_footer_html(pages[1], pages, "../")
    assert 'class="prev-tut"' in html
    assert 'class="next-tut"' in html
    assert 'placeholder' not in html  # no placeholder for middle


def test_footer_edit_on_github_link_present():
    pages = [_tutorial_page(1, "T1"), _tutorial_page(2, "T2")]
    html = _tutorial_footer_html(pages[0], pages, "../")
    assert 'class="edit-on-github"' in html
    assert 'github.com/Pratiyush/llm-wiki/edit/master/docs' in html
    assert 'tutorials/01-x.md' in html
    # Edit link always opens in new tab.
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html


def test_footer_empty_when_page_isnt_in_tutorials():
    pages = [_tutorial_page(1, "T1")]
    other = _page("reference/cli.md", "CLI")
    html = _tutorial_footer_html(other, pages, "../")
    assert html == ""


# ─── compile_docs_site integration ───────────────────────────────────


def _write(root: Path, rel: str, body: str, shell: bool = True) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = "---\ntitle: X\ntype: tutorial\n"
    if shell:
        fm += "docs_shell: true\n"
    fm += "---\n"
    p.write_text(fm + body, encoding="utf-8")
    return p


def test_compile_injects_footer_on_numbered_tutorials(tmp_path: Path):
    _write(tmp_path, "tutorials/01-a.md", "# 01 · A\n\n**Time:** 5 min\n**You'll need:** nothing\n**Result:** done\n\n## Why this matters\nBody.\n")
    _write(tmp_path, "tutorials/02-b.md", "# 02 · B\n\n**Time:** 5 min\n**You'll need:** nothing\n**Result:** done\n\n## Why this matters\nBody.\n")
    site = tmp_path / "site"
    site.mkdir()
    compile_docs_site(tmp_path, site)
    html_1 = (site / "docs" / "tutorials" / "01-a.html").read_text()
    html_2 = (site / "docs" / "tutorials" / "02-b.html").read_text()
    # Both have the footer + edit link.
    for h in (html_1, html_2):
        assert "tutorial-footer" in h
        assert "edit-on-github" in h
    # Tutorial 1 has next → tutorials/02-b.html (no prev).
    assert "02-b.html" in html_1
    # Tutorial 2 has prev → tutorials/01-a.html (no next).
    assert "01-a.html" in html_2


def test_compile_injects_toc_when_enough_headings(tmp_path: Path):
    _write(
        tmp_path,
        "tutorials/01-a.md",
        "# 01 · A\n\n**Time:** 5 min\n**You'll need:** nothing\n**Result:** done\n\n"
        "## Section One\nPara.\n\n## Section Two\nPara.\n\n### Sub A\nPara.\n",
    )
    site = tmp_path / "site"
    site.mkdir()
    compile_docs_site(tmp_path, site)
    out = (site / "docs" / "tutorials" / "01-a.html").read_text()
    assert "tutorial-toc" in out
    assert 'href="#section-one"' in out


def test_compile_omits_toc_when_too_few_headings(tmp_path: Path):
    _write(
        tmp_path,
        "tutorials/01-a.md",
        "# 01 · A\n\n**Time:** 5 min\n**You'll need:** nothing\n**Result:** done\n\n"
        "## Only one section\nPara.\n",
    )
    site = tmp_path / "site"
    site.mkdir()
    compile_docs_site(tmp_path, site)
    out = (site / "docs" / "tutorials" / "01-a.html").read_text()
    assert "tutorial-toc" not in out


def test_compile_skips_footer_on_non_tutorial_pages(tmp_path: Path):
    _write(
        tmp_path, "reference/cli.md",
        "# CLI reference\n\nBody.\n", shell=True,
    )
    site = tmp_path / "site"
    site.mkdir()
    compile_docs_site(tmp_path, site)
    out = (site / "docs" / "reference" / "cli.html").read_text()
    assert "tutorial-footer" not in out
    assert "tutorial-toc" not in out
