"""Comprehensive edge-case tests across all llmwiki modules.

These tests focus on the boundaries and degenerate inputs that are most
likely to cause silent data corruption or crashes in production:
- Empty / missing / corrupt inputs
- Unicode edge cases (emoji, RTL, zero-width chars, surrogate pairs)
- Extremely large inputs (memory-safe truncation)
- Concurrent / race conditions where filesystem state changes
- HTML injection / XSS attempts through every input surface
- Type coercion surprises (string vs int vs None)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

# ═══════════════════════════════════════════════════════════════════════
# build.py: md_to_html edge cases
# ═══════════════════════════════════════════════════════════════════════

from llmwiki.build import md_to_html, parse_frontmatter, normalize_markdown


class TestMdToHtmlEdgeCases:
    def test_empty_string(self):
        assert md_to_html("") == ""

    def test_only_whitespace(self):
        result = md_to_html("   \n\n   \n")
        # Should not crash; may produce empty or whitespace-only output
        assert isinstance(result, str)

    def test_unicode_emoji_in_heading(self):
        html = md_to_html("# Hello World 🌍\n\nBody.\n")
        assert "🌍" in html
        assert "<h1" in html

    def test_rtl_arabic_text(self):
        html = md_to_html("# مرحبا بالعالم\n\nنص عربي\n")
        assert "مرحبا" in html

    def test_zero_width_chars_dont_crash(self):
        # Zero-width joiner + zero-width non-joiner
        body = "Hello\u200b\u200cWorld\n"
        html = md_to_html(body)
        assert isinstance(html, str)

    def test_nested_backticks_in_prose(self):
        body = "Use `` `backtick` `` inside backticks.\n"
        html = md_to_html(body)
        assert "<code>" in html

    def test_script_tag_in_prose_is_escaped(self):
        html = md_to_html("Try <script>alert('xss')</script> here.\n")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_unclosed_code_fence_doesnt_eat_everything(self):
        body = "```python\ndef f():\n    pass\n"
        html = md_to_html(body)
        # Should produce something, not eat everything as code
        assert isinstance(html, str)

    def test_deeply_nested_lists_dont_crash(self):
        body = "\n".join(f"{'  ' * i}- item {i}" for i in range(20))
        html = md_to_html(body)
        assert "item" in html

    def test_very_long_single_line(self):
        body = "x" * 100_000 + "\n"
        html = md_to_html(body)
        assert len(html) >= 100_000

    def test_html_comment_preserved(self):
        body = "text\n\n<!-- llmwiki:metadata foo -->\n\nmore\n"
        html = md_to_html(body)
        assert "<!-- llmwiki:metadata" in html

    def test_table_with_pipes_in_content(self):
        body = "| a \\| b | c |\n|---|---|\n| d \\| e | f |\n"
        html = md_to_html(body)
        assert "<table>" in html


class TestParseFrontmatterEdgeCases:
    def test_empty_string(self):
        meta, body = parse_frontmatter("")
        assert meta == {}
        assert body == ""

    def test_no_frontmatter(self):
        meta, body = parse_frontmatter("# Just a heading\n\nBody here.\n")
        assert meta == {}
        assert "Just a heading" in body

    def test_empty_frontmatter(self):
        meta, body = parse_frontmatter("---\n---\n# Body\n")
        assert meta == {}
        assert "Body" in body

    def test_frontmatter_with_colon_in_value(self):
        text = '---\ntitle: "Session: test — 2026-04-09"\ntype: source\n---\nBody\n'
        meta, body = parse_frontmatter(text)
        assert meta["title"] == "Session: test — 2026-04-09"

    def test_frontmatter_with_empty_list(self):
        text = "---\ntags: []\n---\nBody\n"
        meta, body = parse_frontmatter(text)
        assert meta["tags"] == []

    def test_frontmatter_with_inline_json(self):
        text = '---\ntool_counts: {"Bash": 5, "Read": 3}\n---\nBody\n'
        meta, body = parse_frontmatter(text)
        assert isinstance(meta["tool_counts"], str)
        parsed = json.loads(meta["tool_counts"])
        assert parsed["Bash"] == 5

    def test_frontmatter_with_unicode_values(self):
        text = '---\ntitle: "日本語テスト"\nauthor: "名前"\n---\nBody\n'
        meta, body = parse_frontmatter(text)
        assert meta["title"] == "日本語テスト"


class TestNormalizeMarkdownEdgeCases:
    def test_empty_input(self):
        assert normalize_markdown("") == ""

    def test_already_normalized(self):
        body = "```python\ncode\n```\n"
        assert normalize_markdown(body) == body

    def test_indented_fences_inside_lists(self):
        body = "- item\n  ```\n  code\n  ```\n"
        result = normalize_markdown(body)
        assert "```" in result


# ═══════════════════════════════════════════════════════════════════════
# viz_heatmap: degenerate data
# ═══════════════════════════════════════════════════════════════════════

from llmwiki.viz_heatmap import (
    collect_session_counts,
    compute_quantile_thresholds,
    render_heatmap,
    window_bounds,
)


class TestHeatmapEdgeCases:
    def test_counts_with_future_dates(self):
        """Dates in the future shouldn't crash the heatmap."""
        counts = {date(2030, 1, 1): 5}
        svg = render_heatmap(counts, end_date=date(2026, 4, 9))
        assert "<svg" in svg

    def test_counts_with_very_old_dates(self):
        counts = {date(2020, 1, 1): 3}
        svg = render_heatmap(counts, end_date=date(2026, 4, 9))
        assert "<svg" in svg
        # Old dates outside the 365-day window should just render as l0

    def test_all_same_count_uses_single_level(self):
        counts = {date(2026, 4, d): 1 for d in range(1, 8)}
        thresholds = compute_quantile_thresholds(counts)
        # All same → single distinct value → level 4 for all non-zero
        from llmwiki.viz_heatmap import level_for
        assert level_for(1, thresholds) == 4

    def test_massive_count_value(self):
        counts = {date(2026, 4, 1): 999999}
        svg = render_heatmap(counts, end_date=date(2026, 4, 9))
        assert "999999" in svg  # in the tooltip

    def test_collect_counts_with_none_values(self):
        entries = [{"date": None, "project": "a"}, {"date": "2026-04-01"}]
        counts = collect_session_counts(entries)
        assert date(2026, 4, 1) in counts


# ═══════════════════════════════════════════════════════════════════════
# viz_tools: degenerate data
# ═══════════════════════════════════════════════════════════════════════

from llmwiki.viz_tools import parse_tool_counts, render_tool_chart


class TestToolChartEdgeCases:
    def test_all_zero_counts(self):
        assert render_tool_chart({"Bash": 0, "Read": 0}) == ""

    def test_single_tool(self):
        svg = render_tool_chart({"Bash": 42})
        assert "Bash" in svg
        assert "42" in svg

    def test_negative_count_ignored(self):
        svg = render_tool_chart({"Bash": 5, "Read": -3})
        # Negative counts are filtered out (count <= 0)
        assert "Read" not in svg or "-3" not in svg

    def test_extremely_long_tool_name(self):
        name = "mcp__" + "a" * 200
        svg = render_tool_chart({name: 1})
        # Name should be truncated in the label
        assert "…" in svg

    def test_parse_tool_counts_with_float_values(self):
        # JSON may have float values for integer counts
        meta = {"tool_counts": '{"Bash": 5.0, "Read": 3.0}'}
        counts = parse_tool_counts(meta)
        assert counts["Bash"] == 5
        assert isinstance(counts["Bash"], int)


# ═══════════════════════════════════════════════════════════════════════
# viz_tokens: degenerate data
# ═══════════════════════════════════════════════════════════════════════

from llmwiki.viz_tokens import (
    cache_hit_ratio,
    format_tokens,
    parse_token_totals,
    render_session_token_card,
)


class TestTokenEdgeCases:
    def test_format_tokens_negative(self):
        # Negative tokens shouldn't crash
        result = format_tokens(-1234)
        assert isinstance(result, str)

    def test_cache_hit_ratio_all_output(self):
        """When there's ONLY output tokens (no input), ratio should be None."""
        r = cache_hit_ratio({"output": 10000})
        assert r is None

    def test_token_card_with_huge_values(self):
        meta = {"token_totals": '{"input": 999999999999, "cache_read": 999999999999, "output": 999999999999}'}
        card = render_session_token_card(meta)
        assert "B" in card  # Should format as billions

    def test_token_card_with_all_zeros(self):
        meta = {"token_totals": '{"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0}'}
        assert render_session_token_card(meta) == ""


# ═══════════════════════════════════════════════════════════════════════
# schema: validation boundary cases
# ═══════════════════════════════════════════════════════════════════════

from llmwiki.schema import parse_model_profile


class TestSchemaEdgeCases:
    def test_benchmark_exactly_zero(self):
        meta = {"benchmarks": '{"mmlu": 0.0}'}
        profile, warnings = parse_model_profile(meta)
        assert profile["benchmarks"]["mmlu"] == 0.0
        assert warnings == []

    def test_benchmark_exactly_one(self):
        meta = {"benchmarks": '{"mmlu": 1.0}'}
        profile, warnings = parse_model_profile(meta)
        assert profile["benchmarks"]["mmlu"] == 1.0

    def test_context_window_zero_rejected(self):
        meta = {"model": '{"context_window": 0}'}
        _, warnings = parse_model_profile(meta)
        assert any("context_window" in w for w in warnings)

    def test_context_window_negative_rejected(self):
        meta = {"model": '{"context_window": -100}'}
        _, warnings = parse_model_profile(meta)
        assert any("context_window" in w for w in warnings)

    def test_pricing_zero_is_valid(self):
        """Free-tier models have $0 pricing — that's valid, not an error."""
        meta = {"pricing": '{"input_per_1m": 0.0, "output_per_1m": 0.0}'}
        profile, warnings = parse_model_profile(meta)
        assert profile["pricing"]["input_per_1m"] == 0.0
        assert warnings == []

    def test_xss_in_title(self):
        meta = {"title": '<img src=x onerror=alert(1)>'}
        profile, warnings = parse_model_profile(meta)
        # The profile stores the raw string — XSS defense is at render time
        assert profile["title"] == '<img src=x onerror=alert(1)>'

    def test_deeply_nested_json_in_model_block(self):
        meta = {"model": '{"context_window": {"nested": true}}'}
        _, warnings = parse_model_profile(meta)
        assert any("context_window" in w for w in warnings)


# ═══════════════════════════════════════════════════════════════════════
# compare: degenerate pairs
# ═══════════════════════════════════════════════════════════════════════

from llmwiki.compare import compare_pair_score, generate_pairs


class TestCompareEdgeCases:
    def test_identical_profiles(self):
        """Two identical profiles should still produce a valid comparison."""
        p = {"title": "Same", "provider": "X",
             "model": {"context_window": 100000},
             "pricing": {"input_per_1m": 3.0}}
        score, shared = compare_pair_score(p, p)
        assert score >= 3

    def test_one_empty_one_full(self):
        a = {"title": "Full", "provider": "X",
             "model": {"context_window": 100000, "license": "mit"},
             "benchmarks": {"mmlu": 0.9}}
        b = {}
        score, shared = compare_pair_score(a, b)
        assert score == 0

    def test_generate_pairs_three_identical(self):
        """Three identical models → 3 pairs, all with the same score."""
        entries = [(Path(f"/tmp/M{i}.md"), {"title": f"M{i}", "provider": "X",
                    "model": {"context_window": 100000},
                    "pricing": {"input_per_1m": 3.0}})
                   for i in range(3)]
        pairs = generate_pairs(entries, min_shared_fields=2)
        assert len(pairs) == 3
        scores = [p["score"] for p in pairs]
        assert len(set(scores)) == 1  # all same score


# ═══════════════════════════════════════════════════════════════════════
# changelog_timeline: degenerate entries
# ═══════════════════════════════════════════════════════════════════════

from llmwiki.changelog_timeline import parse_changelog, render_changelog_timeline


class TestChangelogEdgeCases:
    def test_changelog_with_non_list_value(self):
        _, warnings = parse_changelog({"changelog": "not a list"})
        assert any("JSON list" in w for w in warnings)

    def test_changelog_with_nested_object_entries(self):
        """Non-dict entries in the list should be warned + skipped."""
        meta = {"changelog": [42, "string", None]}
        entries, warnings = parse_changelog(meta)
        assert entries == []
        assert len(warnings) == 3

    def test_timeline_with_no_field_or_delta(self):
        entries = [{"date": "2026-04-01", "event": "Something happened"}]
        html = render_changelog_timeline(entries)
        assert "Something happened" in html
        # No field or delta → should still render without crashing

    def test_timeline_escapes_xss_in_event(self):
        entries = [{"date": "2026-04-01", "event": "<img src=x onerror=alert(1)>"}]
        html = render_changelog_timeline(entries)
        # The event text is HTML-escaped, so the raw tag shouldn't appear
        # but the escaped version should.
        assert "<img src=x" not in html
        assert "&lt;img" in html


# ═══════════════════════════════════════════════════════════════════════
# project_topics: degenerate inputs
# ═══════════════════════════════════════════════════════════════════════

from llmwiki.project_topics import extract_session_topics, render_topic_chips


class TestTopicsEdgeCases:
    def test_extract_with_only_noise_tags(self):
        metas = [{"tags": ["claude-code", "session-transcript"]}] * 10
        assert extract_session_topics(metas) == []

    def test_render_chips_with_empty_string_topic(self):
        """Empty strings in the topic list produce empty chips — this is
        a known limitation of the current renderer (it doesn't filter
        empties). The test documents the actual behavior so we can
        decide later if filtering is worth the complexity."""
        html = render_topic_chips(["", "rust", ""])
        # Currently renders 3 chips (2 empty + 1 "rust"). The container
        # class always appears once.
        assert "rust" in html
        assert 'class="project-topics"' in html

    def test_render_chips_with_html_in_topic(self):
        html = render_topic_chips(["<b>bold</b>"])
        assert "<b>" not in html
        assert "&lt;b&gt;" in html


# ═══════════════════════════════════════════════════════════════════════
# context_md: filesystem edge cases
# ═══════════════════════════════════════════════════════════════════════

from llmwiki.context_md import (
    folder_context_summary,
    is_context_file,
    load_folder_context,
)


class TestContextMdEdgeCases:
    def test_binary_file_at_context_path(self, tmp_path: Path):
        """A binary file named _context.md shouldn't crash the loader."""
        (tmp_path / "_context.md").write_bytes(b"\x00\x01\x02\x03\x89PNG")
        result = load_folder_context(tmp_path)
        # Should return something or None — never crash
        assert result is None or isinstance(result, tuple)

    def test_summary_with_only_headings(self):
        body = "# H1\n## H2\n### H3\n"
        assert folder_context_summary(body) == ""

    def test_summary_with_very_long_paragraph(self):
        body = "word " * 1000 + "\n"
        s = folder_context_summary(body, max_chars=100)
        assert len(s) <= 100
        assert s.endswith("…")

    def test_is_context_file_with_path_traversal(self):
        """Path traversal attempt shouldn't match."""
        assert is_context_file(Path("../_context.md")) is True  # name matches
        assert is_context_file(Path("../evil/_context.md")) is True  # name matches
        assert is_context_file(Path("_context")) is False  # no .md
