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


def test_all_13_rules_registered():
    # 11 v1.0 + stale_candidates (v1.1 #51) + cache_tier_consistency (v1.2 #52)
    from llmwiki.lint import rules  # noqa: F401
    assert len(REGISTRY) == 13


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
        "stale_candidates",         # v1.1 (#51)
        "cache_tier_consistency",   # v1.2 (#52)
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
