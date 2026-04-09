"""Tests for `llmwiki.project_topics` — project topics/tag chips."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.project_topics import (
    _NOISE_TAGS,
    extract_session_topics,
    get_project_topics,
    load_project_profile,
    render_topic_chips,
    render_topic_chips_linked,
)


# ─── load_project_profile ────────────────────────────────────────────────


def test_load_project_profile_missing_file_returns_none(tmp_path):
    assert load_project_profile(tmp_path, "nope") is None


def test_load_project_profile_parses_topics_list(tmp_path):
    (tmp_path / "demo-blog-engine.md").write_text(
        "---\ntopics: [rust, blog, ssg]\ndescription: \"Rust SSG demo\"\n---\n\nBody.\n",
        encoding="utf-8",
    )
    profile = load_project_profile(tmp_path, "demo-blog-engine")
    assert profile is not None
    assert profile["topics"] == ["rust", "blog", "ssg"]
    assert profile["description"] == "Rust SSG demo"


def test_load_project_profile_normalizes_topics_lowercase_dedup(tmp_path):
    (tmp_path / "x.md").write_text(
        "---\ntopics: [Rust, rust, BLOG, Blog]\n---\n\nBody.\n",
        encoding="utf-8",
    )
    profile = load_project_profile(tmp_path, "x")
    # Dedup + lowercase + preserve insertion order
    assert profile["topics"] == ["rust", "blog"]


def test_load_project_profile_optional_homepage(tmp_path):
    (tmp_path / "x.md").write_text(
        '---\ntopics: [a]\nhomepage: "https://example.com"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    profile = load_project_profile(tmp_path, "x")
    assert profile["homepage"] == "https://example.com"


def test_load_project_profile_empty_topics(tmp_path):
    (tmp_path / "x.md").write_text(
        "---\ntopics: []\n---\n\nBody.\n", encoding="utf-8"
    )
    profile = load_project_profile(tmp_path, "x")
    assert profile == {"topics": []}


def test_load_project_profile_no_frontmatter_returns_empty_dict(tmp_path):
    (tmp_path / "x.md").write_text("# No frontmatter\n", encoding="utf-8")
    profile = load_project_profile(tmp_path, "x")
    assert profile == {}


# ─── extract_session_topics ──────────────────────────────────────────────


def test_extract_session_topics_filters_noise_tags():
    metas = [
        {"tags": ["claude-code", "session-transcript", "rust"]},
        {"tags": ["claude-code", "session-transcript", "rust"]},
    ]
    assert extract_session_topics(metas) == ["rust"]


def test_extract_session_topics_requires_min_count():
    """A tag in only 1 session is below the default min_count=2 threshold."""
    metas = [
        {"tags": ["rust"]},
        {"tags": ["python"]},
    ]
    assert extract_session_topics(metas) == []


def test_extract_session_topics_sorts_by_frequency():
    metas = [
        {"tags": ["rust", "blog"]},
        {"tags": ["rust", "ssg"]},
        {"tags": ["rust"]},
        {"tags": ["blog"]},
    ]
    result = extract_session_topics(metas)
    # rust=3, blog=2, ssg=1 (below threshold)
    assert result == ["rust", "blog"]


def test_extract_session_topics_respects_max_topics_cap():
    metas = [
        {"tags": [f"tag-{i}"] * 3}  # Each tag in its own dict with 3 counts
        for i in range(20)
    ]
    # Rewrite: each session has one distinct tag, all distinct tags
    metas = [
        {"tags": [f"tag-{i}", f"tag-{i}"]}  # Won't hit min_count=2
        for i in range(20)
    ]
    # Use a controlled dataset: 10 tags each appearing 2 times
    metas = []
    for i in range(10):
        metas.append({"tags": [f"t{i}"]})
        metas.append({"tags": [f"t{i}"]})
    result = extract_session_topics(metas, max_topics=5)
    assert len(result) == 5


def test_extract_session_topics_handles_string_tag_values():
    """If the frontmatter parser gives us a bracketed string instead
    of a list (edge case with manual YAML), we still handle it."""
    metas = [
        {"tags": "[rust, blog]"},
        {"tags": "[rust, blog]"},
    ]
    result = extract_session_topics(metas)
    assert "rust" in result
    assert "blog" in result


def test_extract_session_topics_empty_input():
    assert extract_session_topics([]) == []


def test_noise_tags_constant_includes_core_framework_tags():
    assert "claude-code" in _NOISE_TAGS
    assert "session-transcript" in _NOISE_TAGS


# ─── get_project_topics (precedence) ────────────────────────────────────


def test_get_project_topics_prefers_explicit_profile(tmp_path):
    (tmp_path / "demo.md").write_text(
        "---\ntopics: [explicit1, explicit2]\n---\n\nBody.\n",
        encoding="utf-8",
    )
    metas = [
        {"tags": ["fallback1"]},
        {"tags": ["fallback1"]},
    ]
    result = get_project_topics(tmp_path, "demo", metas)
    assert result == ["explicit1", "explicit2"]


def test_get_project_topics_falls_back_to_session_tags(tmp_path):
    # No file at tmp_path/demo.md
    metas = [
        {"tags": ["fallback-tag"]},
        {"tags": ["fallback-tag"]},
    ]
    result = get_project_topics(tmp_path, "demo", metas)
    assert result == ["fallback-tag"]


def test_get_project_topics_empty_profile_falls_back(tmp_path):
    """A profile file that exists but has no topics (e.g. just a description)
    should still trigger the session-tag fallback rather than returning []."""
    (tmp_path / "demo.md").write_text(
        '---\ndescription: "Just a description"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    metas = [
        {"tags": ["from-sessions"]},
        {"tags": ["from-sessions"]},
    ]
    result = get_project_topics(tmp_path, "demo", metas)
    assert result == ["from-sessions"]


# ─── render_topic_chips ──────────────────────────────────────────────────


def test_render_topic_chips_empty_returns_empty():
    assert render_topic_chips([]) == ""


def test_render_topic_chips_renders_all_when_under_max():
    html_out = render_topic_chips(["rust", "blog", "ssg"])
    assert "rust" in html_out
    assert "blog" in html_out
    assert "ssg" in html_out
    assert "+" not in html_out  # no overflow chip


def test_render_topic_chips_overflow_collapsed_into_more():
    html_out = render_topic_chips([f"tag-{i}" for i in range(10)], max_visible=3)
    assert "tag-0" in html_out
    assert "tag-1" in html_out
    assert "tag-2" in html_out
    assert "tag-3" not in html_out  # hidden
    assert "+7 more" in html_out


def test_render_topic_chips_escapes_html():
    html_out = render_topic_chips(["<script>"])
    assert "<script>" not in html_out.replace("<script>", "")  # won't match raw
    assert "&lt;script&gt;" in html_out


def test_render_topic_chips_uses_custom_classname():
    html_out = render_topic_chips(["a"], classname="session-topics")
    assert 'class="session-topics"' in html_out


# ─── render_topic_chips_linked ──────────────────────────────────────────


def test_render_topic_chips_linked_produces_anchors():
    html_out = render_topic_chips_linked(["rust", "blog"])
    assert html_out.count('<a class="topic-chip"') == 2
    assert 'href="../projects/index.html?topic=rust"' in html_out


def test_render_topic_chips_linked_url_encodes_special_chars():
    """A topic with a space or special char must be URL-encoded in the href."""
    html_out = render_topic_chips_linked(
        ["c++"], href_template="/topics/{topic}.html"
    )
    # `+` becomes %2B when URL-encoded
    assert "c%2B%2B" in html_out or "c%2B%2B.html" in html_out


def test_render_topic_chips_linked_empty():
    assert render_topic_chips_linked([]) == ""
