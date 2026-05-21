from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from llmwiki.notebooks import DEFAULT_NOTEBOOK_SLUG
from llmwiki.web.routes.pages import _wiki_dir_or_404
from llmwiki.web.services import wiki_reader


def _write_page(root: Path, rel: str, title: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\ntype: source\n---\n\n{body}\n',
        encoding="utf-8",
    )
    return path


def test_search_is_scoped_to_wiki_dir(tmp_path: Path) -> None:
    wiki_a = tmp_path / "a" / "wiki"
    wiki_b = tmp_path / "b" / "wiki"
    _write_page(wiki_a, "sources/alpha.md", "Alpha", "alpha scoped content")
    _write_page(wiki_b, "sources/beta.md", "Beta", "alpha leaked content")

    results = wiki_reader.search("alpha", wiki_dir=wiki_a)

    assert [result["path"] for result in results] == ["sources/alpha.md"]


def test_get_tree_is_scoped_to_wiki_dir(tmp_path: Path) -> None:
    wiki_a = tmp_path / "a" / "wiki"
    wiki_b = tmp_path / "b" / "wiki"
    _write_page(wiki_a, "sources/a.md", "A", "only in A")
    _write_page(wiki_b, "sources/b.md", "B", "only in B")

    tree = wiki_reader.get_tree(wiki_dir=wiki_a)

    paths = {page["path"] for pages in tree.values() for page in pages}
    assert "sources/a.md" in paths
    assert "sources/b.md" not in paths


def test_pages_route_defaults_only_when_notebook_missing(monkeypatch, tmp_path: Path) -> None:
    import llmwiki.web.routes.pages as pages

    monkeypatch.setattr(
        pages,
        "notebook_wiki_dir",
        lambda slug: tmp_path / "notebooks" / slug / "wiki",
    )
    default_wiki = tmp_path / "notebooks" / DEFAULT_NOTEBOOK_SLUG / "wiki"
    default_wiki.mkdir(parents=True)

    assert _wiki_dir_or_404(None) == default_wiki

    with pytest.raises(HTTPException) as invalid:
        _wiki_dir_or_404("../bad")
    assert invalid.value.status_code == 404

    with pytest.raises(HTTPException) as missing:
        _wiki_dir_or_404("missing-notebook")
    assert missing.value.status_code == 404
