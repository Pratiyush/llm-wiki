"""Tests for `llmwiki.export_marp` -- Marp slide deck export (v0.7 . #95)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.export_marp import (
    _escape,
    _extract_claims,
    _find_matching_pages,
    _render_slide_deck,
    _slugify,
    export_marp,
)


# ── helpers ──────────────────────────────────────────────────────────────


class TestSlugify:
    def test_simple_topic(self):
        assert _slugify("Reinforcement Learning") == "reinforcement-learning"

    def test_special_characters_stripped(self):
        assert _slugify("RAG (retrieval)") == "rag-retrieval"

    def test_empty_string_returns_untitled(self):
        assert _slugify("") == "untitled"

    def test_whitespace_only_returns_untitled(self):
        assert _slugify("   ") == "untitled"


class TestEscape:
    def test_escapes_angle_brackets(self):
        assert "<" not in _escape("<script>alert(1)</script>")

    def test_escapes_ampersand(self):
        assert _escape("A & B") == "A &amp; B"

    def test_escapes_quotes(self):
        assert _escape('"hello"') == "&quot;hello&quot;"


# ── claim extraction ─────────────────────────────────────────────────────


class TestExtractClaims:
    def test_extracts_key_facts(self):
        page = (
            "## Key Facts\n"
            "- Fact one\n"
            "- Fact two\n"
            "\n"
            "## Connections\n"
        )
        claims = _extract_claims(page)
        assert "Fact one" in claims
        assert "Fact two" in claims

    def test_extracts_key_claims(self):
        page = (
            "## Key Claims\n"
            "- Claim alpha\n"
            "- Claim beta\n"
        )
        claims = _extract_claims(page)
        assert "Claim alpha" in claims
        assert "Claim beta" in claims

    def test_extracts_summary_first_paragraph(self):
        page = (
            "## Summary\n"
            "This session accomplished X.\n"
            "It also did Y.\n"
            "\n"
            "Second paragraph is ignored.\n"
            "\n"
            "## Connections\n"
        )
        claims = _extract_claims(page)
        assert any("accomplished X" in c for c in claims)

    def test_no_sections_returns_empty(self):
        page = "# Title\n\nSome body text.\n"
        claims = _extract_claims(page)
        assert claims == []

    def test_extracts_from_all_sections(self):
        page = (
            "## Key Facts\n"
            "- Fact A\n"
            "\n"
            "## Key Claims\n"
            "- Claim B\n"
            "\n"
            "## Summary\n"
            "Summary text here.\n"
        )
        claims = _extract_claims(page)
        assert len(claims) == 3


# ── page discovery ───────────────────────────────────────────────────────


class TestFindMatchingPages:
    def test_finds_pages_by_title_match(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "sources").mkdir()
        page = wiki / "sources" / "rag-session.md"
        page.write_text("## Summary\nSome RAG content.\n", encoding="utf-8")

        index_text = "## Sources\n- [RAG Session](sources/rag-session.md) -- about RAG\n"
        results = _find_matching_pages("RAG", wiki, index_text)
        assert len(results) == 1
        assert results[0][0] == "RAG Session"

    def test_finds_pages_by_body_match(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "entities").mkdir()
        page = wiki / "entities" / "OpenAI.md"
        page.write_text("## Key Facts\n- Uses reinforcement learning\n", encoding="utf-8")

        index_text = "## Entities\n- [OpenAI](entities/OpenAI.md) -- AI company\n"
        results = _find_matching_pages("reinforcement", wiki, index_text)
        assert len(results) == 1
        assert results[0][0] == "OpenAI"

    def test_no_match_returns_empty(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "sources").mkdir()
        page = wiki / "sources" / "demo.md"
        page.write_text("## Summary\nNothing special.\n", encoding="utf-8")

        index_text = "## Sources\n- [Demo](sources/demo.md) -- demo session\n"
        results = _find_matching_pages("quantum-computing", wiki, index_text)
        assert len(results) == 0

    def test_case_insensitive_match(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        page = wiki / "overview.md"
        page.write_text("## Summary\nAll about RUST and rust.\n", encoding="utf-8")

        index_text = "## Overview\n- [Overview](overview.md)\n"
        results = _find_matching_pages("rust", wiki, index_text)
        assert len(results) == 1


# ── slide rendering ──────────────────────────────────────────────────────


class TestRenderSlideDeck:
    def test_empty_pages_produces_no_pages_found(self):
        deck = _render_slide_deck("Missing Topic", "2026-04-09", [])
        assert "marp: true" in deck
        assert "No pages found" in deck
        assert "Missing Topic" in deck

    def test_marp_frontmatter_present(self):
        deck = _render_slide_deck("Test", "2026-04-09", [])
        assert "marp: true" in deck
        assert "theme: default" in deck
        assert "paginate: true" in deck

    def test_title_slide_has_topic_and_date(self):
        deck = _render_slide_deck("AI Safety", "2026-04-09", [])
        assert "AI Safety" in deck
        assert "2026-04-09" in deck

    def test_pages_produce_content_slides(self):
        pages = [
            ("Page A", ["Claim 1", "Claim 2"]),
            ("Page B", ["Claim 3"]),
            ("Page C", ["Claim 4", "Claim 5", "Claim 6"]),
        ]
        deck = _render_slide_deck("My Topic", "2026-04-09", pages)
        # Title + Outline + 3 content + Summary = at least 6 slide separators
        assert deck.count("---") >= 6
        assert "Page A" in deck
        assert "Page B" in deck
        assert "Page C" in deck
        assert "Claim 1" in deck
        assert "Claim 3" in deck

    def test_outline_slide_lists_all_pages(self):
        pages = [
            ("Alpha", ["x"]),
            ("Beta", ["y"]),
        ]
        deck = _render_slide_deck("Topic", "2026-04-09", pages)
        assert "## Outline" in deck
        assert "Alpha" in deck
        assert "Beta" in deck

    def test_summary_slide_shows_counts(self):
        pages = [
            ("P1", ["c1", "c2"]),
            ("P2", ["c3"]),
        ]
        deck = _render_slide_deck("Topic", "2026-04-09", pages)
        assert "## Summary" in deck
        assert "**2** wiki pages" in deck
        assert "**3** key claims" in deck

    def test_wiki_citations_present(self):
        pages = [("MyPage", ["A claim"])]
        deck = _render_slide_deck("Topic", "2026-04-09", pages)
        assert "[[MyPage]]" in deck


# ── XSS defense ──────────────────────────────────────────────────────────


class TestXSSDefense:
    def test_topic_with_script_tag_is_escaped(self):
        deck = _render_slide_deck(
            '<script>alert("xss")</script>',
            "2026-04-09",
            [],
        )
        assert "<script>" not in deck
        assert "&lt;script&gt;" in deck

    def test_claim_with_html_is_escaped(self):
        pages = [("Page", ['<img src=x onerror="alert(1)">'])]
        deck = _render_slide_deck("Topic", "2026-04-09", pages)
        assert "<img" not in deck
        assert "&lt;img" in deck

    def test_page_title_with_html_is_escaped(self):
        pages = [("<b>Evil</b>", ["A claim"])]
        deck = _render_slide_deck("Topic", "2026-04-09", pages)
        assert "<b>" not in deck
        assert "&lt;b&gt;" in deck


# ── end-to-end export_marp ───────────────────────────────────────────────


class TestExportMarp:
    def test_empty_wiki_produces_deck_with_title_and_no_pages(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Wiki Index\n", encoding="utf-8")

        out = tmp_path / "out" / "deck.marp.md"
        result = export_marp("anything", wiki_dir=wiki, out_path=out)

        assert result == out
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "marp: true" in content
        assert "No pages found" in content

    def test_matching_pages_produce_content_slides(self, tmp_path):
        wiki = tmp_path / "wiki"
        (wiki / "sources").mkdir(parents=True)
        (wiki / "entities").mkdir()
        (wiki / "concepts").mkdir()

        # Create 3 pages about "rust"
        (wiki / "sources" / "rust-blog.md").write_text(
            "## Summary\nBuilt a Rust blog engine.\n\n"
            "## Key Claims\n- Rust is fast\n- Rust is safe\n",
            encoding="utf-8",
        )
        (wiki / "entities" / "Rust.md").write_text(
            "## Key Facts\n- Systems programming language\n- Memory safe\n",
            encoding="utf-8",
        )
        (wiki / "concepts" / "MemorySafety.md").write_text(
            "## Key Facts\n- Rust enforces memory safety at compile time\n",
            encoding="utf-8",
        )

        # Index references all three
        (wiki / "index.md").write_text(
            "# Wiki Index\n\n"
            "## Sources\n"
            "- [Rust Blog](sources/rust-blog.md) -- built a rust blog\n\n"
            "## Entities\n"
            "- [Rust](entities/Rust.md) -- systems language\n\n"
            "## Concepts\n"
            "- [MemorySafety](concepts/MemorySafety.md) -- about rust memory\n",
            encoding="utf-8",
        )

        out = tmp_path / "out" / "rust.marp.md"
        result = export_marp("rust", wiki_dir=wiki, out_path=out)

        content = out.read_text(encoding="utf-8")
        assert "marp: true" in content
        assert "## Outline" in content
        assert "## Summary" in content
        # 3 content slides (one per page)
        assert "Rust Blog" in content
        assert "Rust" in content
        assert "MemorySafety" in content
        # Claims extracted
        assert "Rust is fast" in content
        assert "Systems programming language" in content

    def test_non_matching_topic_produces_no_pages_slide(self, tmp_path):
        wiki = tmp_path / "wiki"
        (wiki / "sources").mkdir(parents=True)
        (wiki / "sources" / "demo.md").write_text(
            "## Summary\nAbout Python.\n", encoding="utf-8"
        )
        (wiki / "index.md").write_text(
            "# Wiki Index\n\n"
            "## Sources\n"
            "- [Demo](sources/demo.md) -- Python session\n",
            encoding="utf-8",
        )

        out = tmp_path / "out" / "quantum.marp.md"
        export_marp("quantum-computing", wiki_dir=wiki, out_path=out)

        content = out.read_text(encoding="utf-8")
        assert "No pages found" in content

    def test_default_output_path_uses_exports_dir(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

        result = export_marp("my topic", wiki_dir=wiki)
        assert result == wiki / "exports" / "my-topic.marp.md"
        assert result.exists()

    def test_output_is_valid_markdown(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

        out = tmp_path / "deck.marp.md"
        export_marp("test", wiki_dir=wiki, out_path=out)

        content = out.read_text(encoding="utf-8")
        # Valid markdown: starts with frontmatter, has headings
        assert content.startswith("---\n")
        assert "# " in content

    def test_xss_in_topic_is_escaped_in_output(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

        out = tmp_path / "xss.marp.md"
        export_marp('<script>alert("xss")</script>', wiki_dir=wiki, out_path=out)

        content = out.read_text(encoding="utf-8")
        assert "<script>" not in content
        assert "&lt;script&gt;" in content


# ── CLI integration ──────────────────────────────────────────────────────


class TestCLI:
    def test_export_marp_subcommand_registered(self):
        from llmwiki.cli import build_parser

        parser = build_parser()
        # Should not raise when parsing export-marp
        args = parser.parse_args(["export-marp", "--topic", "test"])
        assert args.topic == "test"
        assert args.out is None
        assert hasattr(args, "func")

    def test_export_marp_with_all_args(self):
        from llmwiki.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "export-marp",
            "--topic", "RAG",
            "--out", "/tmp/rag.marp.md",
            "--wiki", "/tmp/wiki",
        ])
        assert args.topic == "RAG"
        assert args.out == Path("/tmp/rag.marp.md")
        assert args.wiki == Path("/tmp/wiki")
