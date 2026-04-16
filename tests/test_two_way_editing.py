"""Two-way Obsidian editing verification (v1.0, #158).

Verifies that edits made in Obsidian to symlinked wiki files are:
  1. Picked up by llmwiki tooling (lint, build, categories)
  2. Not overwritten by subsequent llmwiki operations
  3. Preserved through round-trip: load → modify externally → reload

This gives us confidence that the symlink approach (link-obsidian) is
actually bidirectional, not just one-way (llmwiki → Obsidian).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.lint import load_pages, run_all
from llmwiki.categories import scan_tags, generate_static_categories


# ─── Obsidian edit → llmwiki reads it ──────────────────────────────────


def test_user_edit_visible_to_load_pages(tmp_path: Path):
    """When a user edits wiki/ in Obsidian, load_pages() sees the new content."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)

    # llmwiki creates the page
    page = wiki / "entities" / "Foo.md"
    page.write_text(
        '---\ntitle: "Foo"\ntype: entity\nentity_type: tool\n---\n\n# Foo\n',
        encoding="utf-8",
    )

    # User edits in Obsidian — adds a section
    current = page.read_text(encoding="utf-8")
    page.write_text(current + "\n## User Notes\n\nThis is my addition.\n",
                    encoding="utf-8")

    # llmwiki reloads — user edit is visible
    pages = load_pages(wiki)
    assert "## User Notes" in pages["entities/Foo.md"]["body"]
    assert "This is my addition" in pages["entities/Foo.md"]["body"]


def test_user_frontmatter_edit_visible(tmp_path: Path):
    """User can change frontmatter values in Obsidian and llmwiki sees them."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    page = wiki / "entities" / "Foo.md"
    page.write_text(
        '---\ntitle: "Foo"\ntype: entity\nconfidence: 0.5\n---\n\n# Foo\n',
        encoding="utf-8",
    )

    # User reviews and bumps confidence in Obsidian
    page.write_text(
        '---\ntitle: "Foo"\ntype: entity\nconfidence: 0.9\n---\n\n# Foo\n',
        encoding="utf-8",
    )

    pages = load_pages(wiki)
    assert pages["entities/Foo.md"]["meta"]["confidence"] == "0.9"


def test_user_added_tags_affect_category_pages(tmp_path: Path):
    """User adds a tag in Obsidian → category generator picks it up."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "Foo.md").write_text(
        '---\ntitle: "Foo"\ntype: entity\ntags: [flutter]\n---\n\n# Foo\n',
        encoding="utf-8",
    )
    (wiki / "entities" / "Bar.md").write_text(
        '---\ntitle: "Bar"\ntype: entity\ntags: [flutter]\n---\n\n# Bar\n',
        encoding="utf-8",
    )

    pages = load_pages(wiki)
    tags = scan_tags(pages)
    assert "flutter" in tags
    assert len(tags["flutter"]) == 2


def test_user_added_wikilink_resolves(tmp_path: Path):
    """User adds a [[wikilink]] in Obsidian → link integrity rule passes."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "Foo.md").write_text(
        '---\ntitle: "Foo"\ntype: entity\n---\n\n# Foo\n\nSee [[Bar]]\n',
        encoding="utf-8",
    )
    (wiki / "entities" / "Bar.md").write_text(
        '---\ntitle: "Bar"\ntype: entity\n---\n\n# Bar\n',
        encoding="utf-8",
    )

    pages = load_pages(wiki)
    issues = run_all(pages, selected=["link_integrity"])
    broken = [i for i in issues if i["rule"] == "link_integrity"]
    assert broken == []  # No broken links


# ─── Symlink-safe round-trip ─────────────────────────────────────────


def test_load_pages_follows_symlinks(tmp_path: Path):
    """load_pages() follows symlinks — the actual wiki/ path can be symlinked."""
    real_wiki = tmp_path / "real-wiki"
    real_wiki.mkdir()
    (real_wiki / "index.md").write_text(
        '---\ntitle: "Index"\ntype: navigation\n---\n\n# Index\n',
        encoding="utf-8",
    )

    # Create a symlink mimicking link-obsidian
    link = tmp_path / "vault" / "LLM Wiki"
    link.parent.mkdir()
    link.symlink_to(real_wiki, target_is_directory=True)

    # Load via the symlink
    pages_via_link = load_pages(link)
    # Load via the real path
    pages_direct = load_pages(real_wiki)

    assert set(pages_via_link.keys()) == set(pages_direct.keys())
    assert pages_via_link["index.md"]["meta"]["title"] == "Index"


def test_external_edit_then_reload_cycle(tmp_path: Path):
    """Simulate user editing in Obsidian between two llmwiki reads."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    page = wiki / "entities" / "Foo.md"
    page.write_text(
        '---\ntitle: "Foo"\ntype: entity\n---\n\n# Foo\n\nOriginal content.\n',
        encoding="utf-8",
    )

    # 1. llmwiki reads
    pages1 = load_pages(wiki)
    assert "Original content" in pages1["entities/Foo.md"]["body"]

    # 2. User edits in Obsidian
    page.write_text(
        '---\ntitle: "Foo"\ntype: entity\n---\n\n# Foo\n\n'
        'Modified by user.\n\n## Notes\n\nHuman observations.\n',
        encoding="utf-8",
    )

    # 3. llmwiki reads again — sees the update
    pages2 = load_pages(wiki)
    assert "Modified by user" in pages2["entities/Foo.md"]["body"]
    assert "Human observations" in pages2["entities/Foo.md"]["body"]


# ─── Content preservation ────────────────────────────────────────────


def test_user_sections_preserved_through_categories(tmp_path: Path):
    """Generating category pages does not touch source pages."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    page = wiki / "entities" / "Foo.md"
    original = ('---\ntitle: "Foo"\ntype: entity\ntags: [flutter]\n---\n\n'
                '# Foo\n\n## User Notes\n\nDo not touch.\n')
    page.write_text(original, encoding="utf-8")
    page2 = wiki / "entities" / "Bar.md"
    page2.write_text(
        '---\ntitle: "Bar"\ntype: entity\ntags: [flutter]\n---\n\n# Bar\n',
        encoding="utf-8",
    )

    pages = load_pages(wiki)
    cat_dir = tmp_path / "wiki" / "categories"
    generate_static_categories(pages, cat_dir, min_count=2)

    # Source pages must be unchanged
    assert page.read_text(encoding="utf-8") == original


def test_no_accidental_overwrite_of_user_content(tmp_path: Path):
    """lint/dashboard/categories generation never writes back to user pages."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    page = wiki / "entities" / "Foo.md"
    original = ('---\ntitle: "Foo"\ntype: entity\n---\n\n# Foo\n'
                '\n## Custom Section\n\nI wrote this.\n')
    page.write_text(original, encoding="utf-8")

    # Run lint — it never modifies pages
    pages = load_pages(wiki)
    run_all(pages)

    # Page unchanged
    assert page.read_text(encoding="utf-8") == original
