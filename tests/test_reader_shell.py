"""Tests for the reader-first article shell (v1.2.0 · #112)."""

from __future__ import annotations

import re

import pytest

from llmwiki import REPO_ROOT
from llmwiki.reader_shell import (
    INFOBOX_FIELDS_IN_ORDER,
    INFOBOX_FIELD_LABELS,
    READER_SHELL_CSS,
    SHELL_FLAG_FIELD,
    ReaderShellCSS,
    ShellSlots,
    build_slots,
    extract_infobox_fields,
    is_reader_shell_enabled,
    render_article_shell,
)


# ─── Opt-in detection ─────────────────────────────────────────────────


def test_shell_flag_field_is_reader_shell():
    assert SHELL_FLAG_FIELD == "reader_shell"


@pytest.mark.parametrize("value", [True, 1, "true", "TRUE", "yes", "on", "1"])
def test_is_enabled_truthy(value):
    assert is_reader_shell_enabled({SHELL_FLAG_FIELD: value}) is True


@pytest.mark.parametrize("value", [False, 0, "", "no", "false", "maybe", None])
def test_is_enabled_falsy(value):
    meta = {SHELL_FLAG_FIELD: value} if value is not None else {}
    assert is_reader_shell_enabled(meta) is False


def test_is_enabled_missing_key_is_false():
    # The whole point of opt-in — missing = existing behaviour.
    assert is_reader_shell_enabled({}) is False


def test_is_enabled_accepts_other_frontmatter():
    meta = {"title": "X", "type": "entity", SHELL_FLAG_FIELD: True}
    assert is_reader_shell_enabled(meta) is True


# ─── Infobox extraction ───────────────────────────────────────────────


def test_infobox_extracts_known_fields_in_canonical_order():
    meta = {
        "confidence": 0.85,
        "type": "entity",
        "project": "llm-wiki",
        "unknown_field": "dropped",
        "lifecycle": "reviewed",
    }
    fields = extract_infobox_fields(meta)
    keys = list(fields.keys())
    # Known fields present in canonical order:
    assert keys.index("Type") < keys.index("Project")
    assert keys.index("Project") < keys.index("Lifecycle")
    assert keys.index("Lifecycle") < keys.index("Confidence")
    # Unknown fields not included
    assert all("unknown" not in k.lower() for k in keys)


def test_infobox_skips_empty_values():
    meta = {"type": "", "project": None, "model": "claude", "date": []}
    fields = extract_infobox_fields(meta)
    # Only "model" survives — empty string, None, empty list all drop.
    assert "Model" in fields
    assert "Type" not in fields
    assert "Project" not in fields
    assert "Date" not in fields


def test_infobox_formats_confidence_float():
    fields = extract_infobox_fields({"confidence": 0.8})
    assert fields["Confidence"] == "0.80"


def test_infobox_formats_list_as_comma_separated():
    fields = extract_infobox_fields({"project": ["a", "b", "c"]})
    assert fields["Project"] == "a, b, c"


def test_infobox_formats_bool():
    fields = extract_infobox_fields({"type": True})
    assert fields["Type"] == "yes"


def test_infobox_unknown_key_falls_back_to_title_case():
    # Passing a key not in INFOBOX_FIELDS_IN_ORDER should be silently
    # ignored — the extractor's job is *not* to surface everything.
    fields = extract_infobox_fields({"weird_key": "value"})
    assert fields == {}


def test_known_fields_all_have_labels():
    for field in INFOBOX_FIELDS_IN_ORDER:
        assert field in INFOBOX_FIELD_LABELS, (
            f"{field} is in INFOBOX_FIELDS_IN_ORDER but has no label"
        )


# ─── ShellSlots ────────────────────────────────────────────────────────


def test_shell_slots_all_fields_optional():
    slots = ShellSlots()
    # Every list starts empty, every string starts blank — no exceptions
    assert slots.title == ""
    assert slots.body_html == ""
    assert slots.infobox == {}
    assert slots.drawer_links == []
    assert slots.revisions == []
    assert slots.see_also == []
    assert slots.references == []
    assert slots.utility_actions == []


def test_build_slots_auto_extracts_infobox():
    slots = build_slots(
        title="RAG",
        body_html="<p>RAG is retrieval-augmented generation.</p>",
        meta={"type": "concept", "project": "llm-wiki"},
    )
    assert slots.title == "RAG"
    assert "Type" in slots.infobox
    assert "Project" in slots.infobox


def test_build_slots_copies_through_caller_supplied_lists():
    links = [("Karpathy", "/entities/Karpathy.html")]
    slots = build_slots(
        title="RAG",
        body_html="",
        meta={},
        see_also=links,
        references=[("Paper", "https://example.com")],
    )
    assert slots.see_also == links
    assert slots.references == [("Paper", "https://example.com")]


# ─── Rendering ─────────────────────────────────────────────────────────


def test_render_empty_slots_produces_valid_shell_markup():
    out = render_article_shell(ShellSlots())
    assert f'class="{ReaderShellCSS.WRAP}"' in out
    # Drawer is always present (even if empty), so layout stays
    # consistent — but placeholder text must be clear.
    assert ReaderShellCSS.DRAWER in out
    assert "Browse" in out


def test_render_escapes_malicious_title():
    slots = ShellSlots(title="<script>alert(1)</script>")
    out = render_article_shell(slots)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_render_escapes_infobox_values():
    slots = ShellSlots(
        title="X",
        infobox={"Notes": '"<script>"'},
    )
    out = render_article_shell(slots)
    assert "&lt;script&gt;" in out
    assert "&quot;" in out


def test_render_body_html_is_trusted_and_passed_through():
    # Body comes from the build pipeline and is already sanitised —
    # shell must NOT re-escape it.
    body = '<p>Hello <a href="x">world</a>.</p>'
    out = render_article_shell(ShellSlots(body_html=body))
    assert body in out


def test_render_breadcrumbs_last_item_unlinked():
    slots = ShellSlots(
        breadcrumbs=[("Home", "/"), ("Concepts", "/concepts/"), ("RAG", "")],
    )
    out = render_article_shell(slots)
    assert 'aria-current="page">RAG' in out
    assert '<a href="/">Home</a>' in out


def test_render_utility_bar_appears_when_actions_set():
    slots = ShellSlots(
        title="X",
        utility_actions=[("Copy md", "javascript:copy()")],
    )
    out = render_article_shell(slots)
    assert ReaderShellCSS.UTILITY in out
    assert "Copy md" in out


def test_render_utility_bar_hidden_when_empty():
    out = render_article_shell(ShellSlots(title="X"))
    assert ReaderShellCSS.UTILITY not in out


def test_render_empty_sections_collapse():
    out = render_article_shell(ShellSlots(title="X", body_html="<p>body</p>"))
    # Empty see-also / references / revisions don't render
    assert ReaderShellCSS.SEEALSO not in out
    assert ReaderShellCSS.REFERENCES not in out
    assert ReaderShellCSS.REVISIONS not in out


def test_render_infobox_renders_definition_list():
    slots = ShellSlots(infobox={"Type": "entity", "Project": "llm-wiki"})
    out = render_article_shell(slots)
    assert "<dl>" in out
    assert "<dt>Type</dt>" in out
    assert "<dd>entity</dd>" in out


def test_render_see_also_and_references_both_appear():
    slots = ShellSlots(
        see_also=[("Karpathy", "/entities/Karpathy.html")],
        references=[("Paper", "https://example.com")],
    )
    out = render_article_shell(slots)
    assert 'href="/entities/Karpathy.html"' in out
    assert 'href="https://example.com"' in out
    assert "See also" in out
    assert "References" in out


def test_render_revisions_section_renders_time_tags():
    slots = ShellSlots(
        revisions=[
            ("2026-04-17", "Initial ingest"),
            ("2026-04-19", "Added Connections section"),
        ]
    )
    out = render_article_shell(slots)
    assert "<time>2026-04-17</time>" in out
    assert "Initial ingest" in out


def test_render_drawer_empty_shows_placeholder():
    out = render_article_shell(ShellSlots())
    assert "No browse entries configured" in out


def test_render_drawer_with_links():
    slots = ShellSlots(drawer_links=[("Home", "/"), ("Projects", "/projects/")])
    out = render_article_shell(slots)
    assert 'href="/"' in out
    assert "Home" in out
    assert "Projects" in out


def test_render_subtitle_when_set():
    out = render_article_shell(ShellSlots(title="X", subtitle="quick tagline"))
    assert "quick tagline" in out


def test_render_returns_single_wrap_block():
    out = render_article_shell(ShellSlots(title="X"))
    assert out.startswith('<div class="reader-shell">')
    assert out.rstrip().endswith("</div>")
    # Exactly one top-level wrap
    wrap_opens = out.count('<div class="reader-shell">')
    assert wrap_opens == 1


# ─── CSS integration ──────────────────────────────────────────────────


def test_reader_shell_css_is_non_empty():
    assert READER_SHELL_CSS.strip()
    assert ".reader-shell" in READER_SHELL_CSS


def test_reader_shell_css_selectors_namespaced():
    """No naked class selector can leak onto non-reader pages."""
    # Match all `.classname {` blocks — every one must start with
    # `.reader-shell`.
    selectors = re.findall(r"^\s*(\.[A-Za-z0-9_-]+)", READER_SHELL_CSS, re.MULTILINE)
    non_namespaced = [s for s in selectors if not s.startswith(".reader-shell")]
    assert not non_namespaced, (
        f"reader-shell CSS has non-namespaced selectors: {non_namespaced}"
    )


def test_css_variables_referenced_exist_in_main_css():
    """Reader shell shouldn't invent its own CSS variables — it must
    inherit from the brand system (#115)."""
    from llmwiki.render.css import CSS

    used_vars = set(re.findall(r"var\((--[a-z0-9-]+)", READER_SHELL_CSS))
    # Every variable the shell uses must be defined somewhere in the
    # main stylesheet (either on :root or [data-theme="dark"]).
    missing = [v for v in used_vars if f"{v}:" not in CSS]
    assert not missing, (
        f"reader-shell uses undefined CSS variables: {missing}. "
        "Either define them in llmwiki/render/css.py or inherit from "
        "existing tokens."
    )


def test_main_css_includes_reader_shell_css():
    """build.py renders the main CSS into every page — reader-shell
    styles must be appended so opt-in pages actually pick up the layout."""
    from llmwiki.render.css import CSS

    assert ".reader-shell" in CSS, (
        "llmwiki/render/css.py doesn't include the reader-shell CSS — "
        "the append line is missing"
    )


def test_reader_shell_responsive_breakpoints_present():
    # Issue called out mobile layout as an acceptance criterion.
    assert "@media (max-width: 1100px)" in READER_SHELL_CSS
    assert "@media (max-width: 760px)" in READER_SHELL_CSS


# ─── Docs guardrail ───────────────────────────────────────────────────


def test_reader_shell_doc_exists():
    doc = REPO_ROOT / "docs" / "reference" / "reader-shell.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    # Doc must cover the opt-in flag + the slot table + the CSS namespace
    assert SHELL_FLAG_FIELD in text
    assert ".reader-shell" in text
    # Doc must cover the acceptance criteria mentioned in the issue
    for slot in (
        "browse drawer",
        "infobox",
        "references",
        "revisions",
        "see also",
        "utility bar",
    ):
        assert slot in text.lower(), (
            f"reader-shell doc should cover the '{slot}' slot"
        )


# ─── Non-regression: existing pages untouched ────────────────────────


def test_default_render_path_unchanged_for_pages_without_flag():
    """A page without `reader_shell: true` must be treated as NOT
    using the shell — the whole feature is opt-in."""
    assert not is_reader_shell_enabled({"title": "X", "type": "entity"})


def test_css_append_is_additive_not_replace():
    """Main CSS must still contain the pre-#112 content alongside the
    reader-shell additions."""
    from llmwiki.render.css import CSS

    # Known pre-existing selectors from brand system / build output
    for marker in ("--accent", "--font", ".nav-links"):
        assert marker in CSS, (
            f"main CSS lost {marker!r} — the #112 append mutated pre-existing content"
        )
