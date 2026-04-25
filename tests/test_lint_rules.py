"""Tests for the 11 lint rules (v1.0, #155)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.lint import load_pages, run_all, summarize, REGISTRY
from llmwiki.lint.rules import (
    FrontmatterCompleteness,
    FrontmatterValidity,
    LinkIntegrity,
    OrphanDetection,
    ContentFreshness,
    EntityConsistency,
    DuplicateDetection,
    IndexSync,
    ContradictionDetection,
    ClaimVerification,
    SummaryAccuracy,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


def _mk_page(meta: dict, body: str) -> dict:
    fm = "---\n" + "\n".join(f"{k}: {v}" for k, v in meta.items()) + "\n---\n"
    text = fm + body
    return {"path": Path("x"), "rel": "x.md", "text": text, "meta": meta, "body": body}


# ─── Registry ──────────────────────────────────────────────────────────


def test_all_14_rules_registered():
    # 11 v1.0 + stale_candidates (v1.1 #51)
    # + tags_topics_convention (G-16 · #302) + stale_reference_detection (G-17 · #303)
    # + frontmatter_count_consistency (issues.md #2)
    # + tools_consistency (issues.md #4)
    # cache_tier_consistency removed (cache_tiers module deleted)
    from llmwiki.lint import rules  # noqa: F401
    assert len(REGISTRY) == 16


def test_registered_rule_names():
    from llmwiki.lint import rules  # noqa: F401
    expected = {
        "frontmatter_completeness",
        "frontmatter_validity",
        "link_integrity",
        "orphan_detection",
        "content_freshness",
        "entity_consistency",
        "duplicate_detection",
        "index_sync",
        "contradiction_detection",
        "claim_verification",
        "summary_accuracy",
        "stale_candidates",             # v1.1 (#51)
        "tags_topics_convention",       # G-16 · #302
        "stale_reference_detection",    # G-17 · #303
        "frontmatter_count_consistency", # issues.md #2
        "tools_consistency",             # issues.md #4
    }
    assert set(REGISTRY.keys()) == expected


# ─── 12. StaleCandidates — regression for Path import (#51 follow-up) ─


def test_stale_candidates_rule_runs_without_nameerror(tmp_path: Path):
    """Regression: the rule referenced `Path` without importing it, so
    running it against any real page raised NameError (discovered when
    the GH Actions seeded-wiki job failed). Keep this test — if the
    import is dropped again it reproduces immediately.
    """
    from llmwiki.lint.rules import StaleCandidates

    # Build one page that looks like it came from load_pages()
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    entity = wiki / "entities" / "Sample.md"
    entity.write_text(
        "---\ntitle: Sample\ntype: entity\n---\n\nBody.\n", encoding="utf-8"
    )
    pages = {
        "entities/Sample.md": {
            "path": entity,
            "rel": "entities/Sample.md",
            "text": entity.read_text(encoding="utf-8"),
            "meta": {"title": "Sample", "type": "entity"},
            "body": "Body.\n",
        }
    }
    # Should return an empty list (no candidates seeded) instead of raising.
    assert StaleCandidates().run(pages) == []


# ─── 1. FrontmatterCompleteness ──────────────────────────────────────


def test_completeness_happy_path():
    pages = {"a.md": _mk_page({"title": "A", "type": "entity"}, "")}
    issues = FrontmatterCompleteness().run(pages)
    assert issues == []


def test_completeness_missing_fields():
    pages = {"a.md": _mk_page({"title": "A"}, "")}
    issues = FrontmatterCompleteness().run(pages)
    assert len(issues) == 1
    assert "missing" in issues[0]["message"]


def test_completeness_empty_frontmatter():
    pages = {"a.md": _mk_page({}, "")}
    issues = FrontmatterCompleteness().run(pages)
    assert len(issues) == 1


def test_completeness_exempts_system_files():
    """Nav/system files don't need title/type."""
    pages = {
        "index.md": _mk_page({}, ""),
        "log.md": _mk_page({}, ""),
        "overview.md": _mk_page({}, ""),
        "hints.md": _mk_page({}, ""),
        "hot.md": _mk_page({}, ""),
        "MEMORY.md": _mk_page({}, ""),
        "SOUL.md": _mk_page({}, ""),
        "CRITICAL_FACTS.md": _mk_page({}, ""),
        "dashboard.md": _mk_page({}, ""),
    }
    issues = FrontmatterCompleteness().run(pages)
    assert issues == []


def test_completeness_exempts_context_stubs():
    """_context.md stubs don't need title/type."""
    pages = {
        "sources/_context.md": _mk_page({}, ""),
        "entities/_context.md": _mk_page({}, ""),
    }
    issues = FrontmatterCompleteness().run(pages)
    assert issues == []


def test_completeness_still_flags_regular_pages():
    """Non-system pages still need title/type."""
    pages = {
        "entities/Foo.md": _mk_page({}, ""),
        "index.md": _mk_page({}, ""),  # exempt
    }
    issues = FrontmatterCompleteness().run(pages)
    assert len(issues) == 1
    assert issues[0]["page"] == "entities/Foo.md"


# ─── 2. FrontmatterValidity ──────────────────────────────────────────


def test_validity_good_values():
    pages = {"a.md": _mk_page({
        "title": "A", "type": "entity", "lifecycle": "draft",
        "entity_type": "tool", "confidence": "0.8"
    }, "")}
    issues = FrontmatterValidity().run(pages)
    assert issues == []


def test_validity_bad_type():
    pages = {"a.md": _mk_page({"title": "A", "type": "dinosaur"}, "")}
    issues = FrontmatterValidity().run(pages)
    assert any("invalid type" in i["message"] for i in issues)


def test_validity_bad_lifecycle():
    pages = {"a.md": _mk_page({"title": "A", "type": "entity",
                                "lifecycle": "bogus"}, "")}
    issues = FrontmatterValidity().run(pages)
    assert any("invalid lifecycle" in i["message"] for i in issues)


def test_validity_bad_entity_type():
    pages = {"a.md": _mk_page({"title": "A", "type": "entity",
                                "entity_type": "dinosaur"}, "")}
    issues = FrontmatterValidity().run(pages)
    assert any("invalid entity_type" in i["message"] for i in issues)


def test_validity_confidence_out_of_range():
    pages = {"a.md": _mk_page({"title": "A", "type": "entity",
                                "confidence": "1.5"}, "")}
    issues = FrontmatterValidity().run(pages)
    assert any("out of range" in i["message"] for i in issues)


def test_validity_confidence_not_numeric():
    pages = {"a.md": _mk_page({"title": "A", "type": "entity",
                                "confidence": "high"}, "")}
    issues = FrontmatterValidity().run(pages)
    assert any("not numeric" in i["message"] for i in issues)


# ─── 3. LinkIntegrity ────────────────────────────────────────────────


def test_links_resolve():
    pages = {
        "entities/Foo.md": _mk_page({"title": "Foo"}, "See [[Bar]]"),
        "entities/Bar.md": _mk_page({"title": "Bar"}, ""),
    }
    issues = LinkIntegrity().run(pages)
    assert issues == []


def test_broken_link():
    pages = {
        "entities/Foo.md": _mk_page({"title": "Foo"}, "See [[Nowhere]]"),
    }
    issues = LinkIntegrity().run(pages)
    assert len(issues) == 1
    assert "Nowhere" in issues[0]["message"]


def test_link_with_anchor_resolves():
    pages = {
        "entities/Foo.md": _mk_page({"title": "Foo"}, "See [[Bar#section]]"),
        "entities/Bar.md": _mk_page({"title": "Bar"}, ""),
    }
    issues = LinkIntegrity().run(pages)
    assert issues == []


# ─── 4. OrphanDetection ──────────────────────────────────────────────


def test_orphan_found():
    pages = {
        "entities/Foo.md": _mk_page({"title": "Foo"}, "content"),
    }
    issues = OrphanDetection().run(pages)
    assert len(issues) == 1
    assert "orphan" in issues[0]["message"]


def test_non_orphan():
    pages = {
        "entities/Foo.md": _mk_page({"title": "Foo"}, "See [[Bar]]"),
        "entities/Bar.md": _mk_page({"title": "Bar"}, ""),
    }
    issues = OrphanDetection().run(pages)
    # Foo has no inbound, Bar has 1 inbound
    orphans = [i for i in issues if i["rule"] == "orphan_detection"]
    assert len(orphans) == 1
    assert "Foo" in orphans[0]["page"]


def test_nav_files_not_orphan_candidates():
    pages = {
        "index.md": _mk_page({"title": "Index"}, ""),
        "overview.md": _mk_page({"title": "Overview"}, ""),
    }
    issues = OrphanDetection().run(pages)
    assert issues == []  # nav files skipped


# ─── 5. ContentFreshness ─────────────────────────────────────────────


def test_fresh_page():
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    pages = {"a.md": _mk_page({"title": "A", "last_updated": recent}, "")}
    issues = ContentFreshness().run(pages)
    assert issues == []


def test_stale_page():
    from datetime import datetime, timezone, timedelta
    old = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d")
    pages = {"a.md": _mk_page({"title": "A", "last_updated": old}, "")}
    issues = ContentFreshness().run(pages)
    assert len(issues) == 1
    assert "days ago" in issues[0]["message"]


def test_no_date_no_issue():
    pages = {"a.md": _mk_page({"title": "A"}, "")}
    issues = ContentFreshness().run(pages)
    assert issues == []


# ─── 6. EntityConsistency ────────────────────────────────────────────


def test_entity_with_type():
    pages = {"entities/Foo.md": _mk_page({
        "title": "Foo", "type": "entity", "entity_type": "tool"
    }, "")}
    issues = EntityConsistency().run(pages)
    assert issues == []


def test_entity_missing_entity_type():
    pages = {"entities/Foo.md": _mk_page({
        "title": "Foo", "type": "entity"
    }, "")}
    issues = EntityConsistency().run(pages)
    assert len(issues) == 1


def test_non_entity_pages_skipped():
    pages = {"concepts/Idea.md": _mk_page({
        "title": "Idea", "type": "concept"
    }, "")}
    issues = EntityConsistency().run(pages)
    assert issues == []


# ─── 7. DuplicateDetection ───────────────────────────────────────────


def test_no_duplicates():
    pages = {
        "a.md": _mk_page({"title": "Apple"}, ""),
        "b.md": _mk_page({"title": "Banana"}, ""),
    }
    issues = DuplicateDetection().run(pages)
    assert issues == []


def test_exact_duplicates():
    # G-11 (#297): rule now requires BOTH title AND body overlap AND same
    # project before flagging. Empty bodies are intentionally skipped to
    # avoid flooding reports on templated boilerplate files.
    shared_body = "Real duplicate content shared by both pages. " * 20
    pages = {
        "a.md": _mk_page(
            {"title": "Claude Code", "type": "source", "project": "proj"},
            shared_body,
        ),
        "b.md": _mk_page(
            {"title": "Claude Code", "type": "source", "project": "proj"},
            shared_body,
        ),
    }
    issues = DuplicateDetection().run(pages)
    assert len(issues) == 1


def test_similar_titles():
    # Same project + near-identical titles + highly-overlapping bodies.
    shared_body = "Claude Code CLI is a tool for building agents. " * 30
    pages = {
        "a.md": _mk_page(
            {"title": "Claude Code CLI", "type": "source", "project": "proj"},
            shared_body,
        ),
        "b.md": _mk_page(
            {"title": "Claude Code CLI!", "type": "source", "project": "proj"},
            shared_body + "!",
        ),
    }
    issues = DuplicateDetection().run(pages)
    assert len(issues) >= 1


# ─── 8. IndexSync ────────────────────────────────────────────────────


def test_index_listed_page_exists():
    pages = {
        "index.md": _mk_page({"title": "Index"},
                             "- [Foo](entities/Foo.md)"),
        "entities/Foo.md": _mk_page({"title": "Foo"}, ""),
    }
    issues = IndexSync().run(pages)
    assert issues == []


def test_index_dead_link():
    pages = {
        "index.md": _mk_page({"title": "Index"},
                             "- [Nonexistent](entities/Nope.md)"),
    }
    issues = IndexSync().run(pages)
    assert any("dead index link" in i["message"] for i in issues)


def test_index_missing_page():
    pages = {
        "index.md": _mk_page({"title": "Index"}, ""),
        "entities/Foo.md": _mk_page({"title": "Foo"}, ""),
    }
    issues = IndexSync().run(pages)
    assert any("not listed in index" in i["message"] for i in issues)


# ─── #411 — IndexSync href resolution edge cases ─────────────────────


def test_index_dot_slash_prefix_resolves():
    """Regression for #411: `./entities/Foo.md` happened to work via
    `lstrip('./')`. Keep the test so the new resolver still handles it."""
    pages = {
        "index.md": _mk_page({"title": "Index"},
                             "- [Foo](./entities/Foo.md)"),
        "entities/Foo.md": _mk_page({"title": "Foo"}, ""),
    }
    issues = IndexSync().run(pages)
    assert all("dead index link" not in i["message"] for i in issues)


def test_index_anchor_resolves():
    """Regression for #411: `entities/Foo.md#section` was treated as a
    dead link because anchor wasn't stripped before the lookup."""
    pages = {
        "index.md": _mk_page({"title": "Index"},
                             "- [Foo](entities/Foo.md#section)"),
        "entities/Foo.md": _mk_page({"title": "Foo"}, ""),
    }
    issues = IndexSync().run(pages)
    assert all("dead index link" not in i["message"] for i in issues)


def test_index_query_string_resolves():
    """Regression for #411: `entities/Foo.md?v=2` was a false positive."""
    pages = {
        "index.md": _mk_page({"title": "Index"},
                             "- [Foo](entities/Foo.md?v=2)"),
        "entities/Foo.md": _mk_page({"title": "Foo"}, ""),
    }
    issues = IndexSync().run(pages)
    assert all("dead index link" not in i["message"] for i in issues)


def test_index_anchor_and_query_combined():
    """Both `#anchor` and `?query` together — both must be stripped."""
    pages = {
        "index.md": _mk_page({"title": "Index"},
                             "- [Foo](entities/Foo.md?v=2#section)"),
        "entities/Foo.md": _mk_page({"title": "Foo"}, ""),
    }
    issues = IndexSync().run(pages)
    assert all("dead index link" not in i["message"] for i in issues)


def test_index_dotdot_collapse():
    """`../entities/Foo.md` from a hypothetical sub-index normalises by
    collapsing the `..`. Index.md is at root so leading `..` escapes
    and the resolver returns "" → href is silently dropped (treated
    as unresolvable, but the missing-page check would catch it)."""
    pages = {
        "index.md": _mk_page({"title": "Index"},
                             "- [Foo](../entities/Foo.md)"),
        "entities/Foo.md": _mk_page({"title": "Foo"}, ""),
    }
    issues = IndexSync().run(pages)
    # The `..` escapes the wiki root so the resolver returns "" and
    # we don't even try to validate. The missing-page check still
    # surfaces "not listed" for entities/Foo.md, which is the correct
    # signal — the index author needs to fix the malformed href.
    assert any("not listed in index" in i["message"] for i in issues)


def test_index_external_links_still_skipped():
    """https://, http://, and mailto: URLs must not be resolved at all."""
    pages = {
        "index.md": _mk_page({"title": "Index"}, """
- [Anthropic](https://anthropic.com)
- [HTTP](http://example.com/foo)
- [Email](mailto:hi@example.com)
- [Foo](entities/Foo.md)
"""),
        "entities/Foo.md": _mk_page({"title": "Foo"}, ""),
    }
    issues = IndexSync().run(pages)
    # Only entities/Foo.md is a real link and it resolves.
    assert all("dead index link" not in i["message"] for i in issues)


def test_index_dead_link_still_flagged_after_resolver():
    """Sanity: real dead links (target doesn't exist) still flag."""
    pages = {
        "index.md": _mk_page({"title": "Index"},
                             "- [Nope](entities/DoesNotExist.md)"),
    }
    issues = IndexSync().run(pages)
    assert any("dead index link" in i["message"] for i in issues)


def test_index_dead_link_with_anchor_still_flagged():
    """Anchors don't help a non-existent page resolve."""
    pages = {
        "index.md": _mk_page({"title": "Index"},
                             "- [Nope](entities/DoesNotExist.md#section)"),
    }
    issues = IndexSync().run(pages)
    assert any("dead index link" in i["message"] for i in issues)


def test_resolve_index_href_unit():
    """Direct unit test for the href resolver covering the matrix."""
    from llmwiki.lint.rules import _resolve_index_href
    assert _resolve_index_href("entities/Foo.md") == "entities/Foo.md"
    assert _resolve_index_href("./entities/Foo.md") == "entities/Foo.md"
    assert _resolve_index_href("entities/Foo.md#section") == "entities/Foo.md"
    assert _resolve_index_href("entities/Foo.md?v=2") == "entities/Foo.md"
    assert _resolve_index_href("entities/Foo.md?v=2#section") == "entities/Foo.md"
    assert _resolve_index_href("a/b/../c.md") == "a/c.md"
    assert _resolve_index_href("../escapes.md") == ""  # escapes root
    assert _resolve_index_href("") == ""
    assert _resolve_index_href("#anchor-only") == ""
    assert _resolve_index_href("./") == ""
    # Nested current-dir references collapse.
    assert _resolve_index_href("./a/./b.md") == "a/b.md"


# ─── 9-11. LLM-powered rules (stubs) ────────────────────────────────


def test_contradiction_without_llm_callback():
    pages = {"a.md": _mk_page({"title": "A"}, "")}
    issues = ContradictionDetection().run(pages)
    # Without llm_callback, returns a "skipped" info message
    assert len(issues) == 1
    assert issues[0]["severity"] == "info"
    assert "requires LLM" in issues[0]["message"]


def test_contradiction_detects_section():
    pages = {
        "a.md": _mk_page({"title": "A"},
                         "## Contradictions\n- X says yes, Y says no\n"),
    }
    issues = ContradictionDetection().run(pages, llm_callback=lambda p: "")
    assert len(issues) == 1


def test_claim_verification_without_callback():
    pages = {"a.md": _mk_page({"title": "A"}, "")}
    issues = ClaimVerification().run(pages)
    assert len(issues) == 1
    assert "requires LLM" in issues[0]["message"]


def test_claim_verification_detects_unsourced():
    pages = {
        "entities/Foo.md": _mk_page(
            {"title": "Foo", "type": "entity"},
            "## Key Facts\n- Some claim with no source\n",
        ),
    }
    issues = ClaimVerification().run(pages, llm_callback=lambda p: "")
    assert len(issues) == 1


def test_summary_accuracy_without_callback():
    pages = {"a.md": _mk_page({"title": "A"}, "")}
    issues = SummaryAccuracy().run(pages)
    assert len(issues) == 1


def test_summary_accuracy_empty_summary():
    pages = {"a.md": _mk_page({"title": "A", "summary": ""}, "")}
    issues = SummaryAccuracy().run(pages, llm_callback=lambda p: "")
    assert len(issues) == 1
    assert "empty" in issues[0]["message"]


# ─── Runner ──────────────────────────────────────────────────────────


def test_run_all_basic_only():
    pages = {
        "index.md": _mk_page({"title": "Index"}, ""),
        "entities/Foo.md": _mk_page({"title": "Foo"}, ""),  # missing type
    }
    issues = run_all(pages, include_llm=False)
    # Should find frontmatter completeness issues but not LLM stubs
    rule_names = {i["rule"] for i in issues}
    assert "frontmatter_completeness" in rule_names
    # LLM rules skipped when include_llm=False
    assert "contradiction_detection" not in rule_names


def test_run_all_include_llm():
    pages = {"a.md": _mk_page({"title": "A", "type": "entity"}, "")}
    issues = run_all(pages, include_llm=True)
    rule_names = {i["rule"] for i in issues}
    # LLM rules run but return skipped info
    assert "contradiction_detection" in rule_names


def test_run_all_selected():
    pages = {"a.md": _mk_page({"title": "A"}, "")}
    issues = run_all(pages, selected=["frontmatter_completeness"])
    rule_names = {i["rule"] for i in issues}
    assert rule_names == {"frontmatter_completeness"}


def test_summarize():
    issues = [
        {"severity": "error", "rule": "r1", "page": "p", "message": "m"},
        {"severity": "error", "rule": "r2", "page": "p", "message": "m"},
        {"severity": "warning", "rule": "r3", "page": "p", "message": "m"},
    ]
    summary = summarize(issues)
    assert summary == {"error": 2, "warning": 1}


# ─── load_pages ──────────────────────────────────────────────────────


def test_load_pages_empty_dir(tmp_path: Path):
    assert load_pages(tmp_path) == {}


def test_load_pages_missing_dir():
    assert load_pages(Path("/nonexistent/dir")) == {}


def test_load_pages_reads_markdown(tmp_path: Path):
    (tmp_path / "entities").mkdir()
    (tmp_path / "entities" / "Foo.md").write_text(
        '---\ntitle: "Foo"\ntype: entity\n---\n\n# Foo\n', encoding="utf-8"
    )
    pages = load_pages(tmp_path)
    assert "entities/Foo.md" in pages
    assert pages["entities/Foo.md"]["meta"]["title"] == "Foo"
    assert pages["entities/Foo.md"]["meta"]["type"] == "entity"


# ─── frontmatter_count_consistency (issues.md #2) ───────────────────────


def test_count_consistency_flags_inflated_user_messages():
    body = "### Turn 1 — User\nhi\n\n### Turn 2 — User\nhello\n"
    page = _mk_page(
        {"title": "s", "type": "source", "user_messages": 6, "turn_count": 6,
         "tool_calls": 0},
        body,
    )
    issues = run_all({"sources/s.md": page},
                     selected=["frontmatter_count_consistency"])
    messages = {i["message"] for i in issues}
    assert any("user_messages=6 but body has 2" in m for m in messages)
    assert any("turn_count=6 but body has 2" in m for m in messages)


def test_count_consistency_passes_when_counts_match():
    body = "### Turn 1 — User\nhi\n- `Bash`: ls\n- `Write`: /tmp/x\n"
    page = _mk_page(
        {"title": "s", "type": "source", "user_messages": 1, "turn_count": 1,
         "tool_calls": 2},
        body,
    )
    issues = run_all({"sources/s.md": page},
                     selected=["frontmatter_count_consistency"])
    assert issues == []


def test_count_consistency_skips_non_source_pages():
    body = "### Turn 1 — User\nhi\n"
    page = _mk_page(
        {"title": "e", "type": "entity", "user_messages": 99},
        body,
    )
    issues = run_all({"entities/e.md": page},
                     selected=["frontmatter_count_consistency"])
    assert issues == []


# ─── tools_consistency (issues.md #4) ────────────────────────────────────


def test_tools_consistency_flags_missing_tool_count_entry():
    body = "# s"
    page = _mk_page(
        {
            "title": "s", "type": "source",
            "tools_used": "[Read, Write, Grep]",
            "tool_counts": '{"Read": 1, "Write": 2}',
        },
        body,
    )
    issues = run_all({"sources/s.md": page}, selected=["tools_consistency"])
    assert any("['Grep']" in i["message"] for i in issues)


def test_tools_consistency_passes_when_sets_match():
    body = "# s"
    page = _mk_page(
        {
            "title": "s", "type": "source",
            "tools_used": "[Read, Write]",
            "tool_counts": '{"Read": 1, "Write": 2}',
        },
        body,
    )
    issues = run_all({"sources/s.md": page}, selected=["tools_consistency"])
    assert issues == []


def test_tools_consistency_flags_extra_tool_count_key():
    """The reverse direction — tool_counts has a key that tools_used omits."""
    body = "# s"
    page = _mk_page(
        {
            "title": "s", "type": "source",
            "tools_used": "[Read]",
            "tool_counts": '{"Read": 1, "Bash": 3}',
        },
        body,
    )
    issues = run_all({"sources/s.md": page}, selected=["tools_consistency"])
    assert any("['Bash']" in i["message"] for i in issues)


# ─── #410 — tools_used type-coercion (regression for the TypeError) ──


def test_tools_consistency_handles_list_tools_used():
    """Regression for #410: when frontmatter is parsed by `_frontmatter.py`'s
    inline-list path, `tools_used` comes back as a real Python list, not a
    string. Old code did `re.search(regex, list)` and raised TypeError —
    silently aborting the whole rule."""
    body = "# s"
    page = _mk_page({}, body)
    page["meta"] = {
        "title": "s", "type": "source",
        "tools_used": ["Read", "Write", "Grep"],  # list, not str
        "tool_counts": '{"Read": 1, "Write": 2}',
    }
    issues = run_all({"sources/s.md": page}, selected=["tools_consistency"])
    assert any("['Grep']" in i["message"] for i in issues), (
        f"list-typed tools_used didn't surface the missing-key warning: {issues}"
    )


def test_tools_consistency_handles_quoted_list_elements():
    """tools_used: [\"Read\", \"Write\"] — quoted elements get unquoted."""
    body = "# s"
    page = _mk_page({}, body)
    page["meta"] = {
        "title": "s", "type": "source",
        "tools_used": ['"Read"', '"Write"'],
        "tool_counts": '{"Read": 1, "Write": 2}',
    }
    issues = run_all({"sources/s.md": page}, selected=["tools_consistency"])
    assert issues == [], (
        f"quoted list elements caused false positives: {issues}"
    )


def test_tools_consistency_handles_empty_list():
    """tools_used: [] should be treated like tools_used missing."""
    body = "# s"
    page = _mk_page({}, body)
    page["meta"] = {
        "title": "s", "type": "source",
        "tools_used": [],
        "tool_counts": '{"Read": 1}',
    }
    issues = run_all({"sources/s.md": page}, selected=["tools_consistency"])
    assert issues == []


def test_tools_consistency_handles_dict_tool_counts():
    """tool_counts can be a real dict (after JSON parsing) — must work."""
    body = "# s"
    page = _mk_page({}, body)
    page["meta"] = {
        "title": "s", "type": "source",
        "tools_used": ["Read", "Write"],
        "tool_counts": {"Read": 1, "Write": 2, "Bash": 3},
    }
    issues = run_all({"sources/s.md": page}, selected=["tools_consistency"])
    assert any("['Bash']" in i["message"] for i in issues)


def test_tools_consistency_skips_unsupported_types():
    """Numbers, bools, dicts in tools_used → silently skip (not crash)."""
    for hostile in [42, True, {"unexpected": "shape"}]:
        page = _mk_page({}, "# s")
        page["meta"] = {
            "title": "s", "type": "source",
            "tools_used": hostile,
            "tool_counts": '{"Read": 1}',
        }
        # Must not raise.
        issues = run_all({"sources/s.md": page}, selected=["tools_consistency"])
        # And must not flag — we have no idea what to compare against.
        assert issues == [], (
            f"unsupported tools_used={hostile!r} produced spurious issue: {issues}"
        )


def test_tools_consistency_unit_normalise_tools_used():
    """Direct unit test for the helper — covers the type matrix in one shot."""
    from llmwiki.lint.rules import _normalise_tools_used
    assert _normalise_tools_used(None) == set()
    assert _normalise_tools_used("") == set()
    assert _normalise_tools_used([]) == set()
    assert _normalise_tools_used(["Read", "Write"]) == {"Read", "Write"}
    assert _normalise_tools_used(['"Read"', "'Write'"]) == {"Read", "Write"}
    assert _normalise_tools_used("[Read, Write]") == {"Read", "Write"}
    assert _normalise_tools_used('["Read", "Write"]') == {"Read", "Write"}
    assert _normalise_tools_used("not a list") == set()
    assert _normalise_tools_used(42) == set()
    assert _normalise_tools_used(True) == set()
    assert _normalise_tools_used({"unexpected": "shape"}) == set()


def test_tools_consistency_unit_normalise_tool_counts_keys():
    from llmwiki.lint.rules import _normalise_tool_counts_keys
    assert _normalise_tool_counts_keys(None) == set()
    assert _normalise_tool_counts_keys("") == set()
    assert _normalise_tool_counts_keys({}) == set()
    assert _normalise_tool_counts_keys({"Read": 1}) == {"Read"}
    assert _normalise_tool_counts_keys('{"Read": 1, "Write": 2}') == {"Read", "Write"}
    assert _normalise_tool_counts_keys(42) == set()
