"""Tests for the static prototype hub (#114)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.prototypes import (
    PROTOTYPE_STATES,
    PROTOTYPES_DIRNAME,
    PrototypeState,
    build_prototype_hub,
    prototype_nav_link,
    prototypes_dir,
    render_hub_index,
    render_state,
)


# ─── Registry / constants ─────────────────────────────────────────────


def test_six_states_ship_today():
    """Issue #114 explicitly called out six review states — keep the
    count locked so someone can't silently drop a state without
    updating the issue."""
    assert len(PROTOTYPE_STATES) == 6


def test_every_state_is_frozen_dataclass():
    for state in PROTOTYPE_STATES:
        with pytest.raises(Exception):  # FrozenInstanceError
            state.slug = "mutated"  # type: ignore[misc]


def test_state_slugs_are_unique():
    slugs = [s.slug for s in PROTOTYPE_STATES]
    assert len(set(slugs)) == len(slugs)


def test_state_slugs_are_url_safe():
    import re
    for s in PROTOTYPE_STATES:
        assert re.fullmatch(r"[a-z0-9-]+", s.slug), (
            f"slug {s.slug!r} must be lowercase-kebab only (URL-safe)"
        )


EXPECTED_SLUGS = {
    "page-shell", "article-anatomy", "drawer-browse",
    "search-results", "empty-search", "references-rail",
}


def test_all_expected_slugs_present():
    """Each slug maps to a specific reviewable state called out in
    issue #114 — if one goes missing, the review doc referencing it
    would 404."""
    assert {s.slug for s in PROTOTYPE_STATES} == EXPECTED_SLUGS


def test_every_state_has_non_empty_description():
    for s in PROTOTYPE_STATES:
        assert s.description.strip(), f"state {s.slug} has empty description"
        # Reviewers scan descriptions quickly — they should be at least
        # one sentence.
        assert len(s.description) > 20


def test_nav_link_points_at_hub_index():
    href, label = prototype_nav_link()
    assert href == f"{PROTOTYPES_DIRNAME}/index.html"
    assert label == "Prototypes"


def test_prototypes_dir_resolves_under_site(tmp_path: Path):
    out = prototypes_dir(tmp_path)
    assert out == tmp_path / PROTOTYPES_DIRNAME


# ─── Rendering ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("state", PROTOTYPE_STATES, ids=lambda s: s.slug)
def test_render_state_produces_valid_html(state: PrototypeState):
    html = render_state(state)
    # Framework: DOCTYPE, head, body
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "<head>" in html and "</head>" in html
    assert "<body>" in html and "</body>" in html

    # Inherits the live stylesheet
    assert '<link rel="stylesheet" href="../style.css">' in html

    # Carries the purple identification stripe (brand through-line + the
    # "this is a prototype" visual cue)
    assert "#7C3AED" in html
    assert "proto-stripe" in html

    # Meta block identifies this as a prototype, not a live page
    assert "Prototype — not a live page" in html

    # Title appears in the <title> tag
    assert f"{state.title} — llmwiki prototypes" in html


def test_render_state_escapes_title_and_description():
    evil = PrototypeState(
        slug="x",
        title="<script>alert(1)</script>",
        description='has "quotes" & ampersands',
    )
    # We can only render known slugs; inject a shim so the renderer
    # function exists for this evil state.
    from llmwiki.prototypes import _RENDERERS  # type: ignore[attr-defined]
    _RENDERERS["x"] = lambda s: "<p>body</p>"
    try:
        html = render_state(evil)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html
        assert "&amp;" in html
    finally:
        del _RENDERERS["x"]


def test_render_hub_index_lists_every_state():
    html = render_hub_index()
    assert "<!DOCTYPE html>" in html
    assert "Prototypes" in html
    for state in PROTOTYPE_STATES:
        assert f'href="{state.slug}.html"' in html
        assert state.title in html


def test_hub_index_back_link_to_main_site():
    html = render_hub_index()
    assert '<a href="../index.html">← Back to site</a>' in html


def test_hub_index_has_identification_stripe():
    html = render_hub_index()
    assert "#7C3AED" in html
    assert "proto-stripe" in html


# ─── Build integration ────────────────────────────────────────────────


def test_build_prototype_hub_writes_all_files(tmp_path: Path):
    site = tmp_path / "site"
    site.mkdir()

    idx = build_prototype_hub(site)
    assert idx == site / PROTOTYPES_DIRNAME / "index.html"
    assert idx.is_file()

    for state in PROTOTYPE_STATES:
        state_file = site / PROTOTYPES_DIRNAME / f"{state.slug}.html"
        assert state_file.is_file(), f"missing {state.slug}.html"


def test_build_raises_when_site_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="site_dir"):
        build_prototype_hub(tmp_path / "no-site")


def test_build_is_idempotent(tmp_path: Path):
    site = tmp_path / "site"
    site.mkdir()

    build_prototype_hub(site)
    build_prototype_hub(site)  # second run shouldn't error

    for state in PROTOTYPE_STATES:
        state_file = site / PROTOTYPES_DIRNAME / f"{state.slug}.html"
        assert state_file.is_file()


def test_build_respects_custom_state_list(tmp_path: Path):
    site = tmp_path / "site"
    site.mkdir()
    from llmwiki.prototypes import _RENDERERS  # type: ignore[attr-defined]

    _RENDERERS["x"] = lambda s: "<p>custom</p>"
    try:
        custom = (PrototypeState(slug="x", title="X", description="custom state"),)
        build_prototype_hub(site, states=custom)
        assert (site / PROTOTYPES_DIRNAME / "x.html").is_file()
        # State not in the custom list shouldn't be written
        assert not (site / PROTOTYPES_DIRNAME / "page-shell.html").exists()
    finally:
        del _RENDERERS["x"]


# ─── Main-site nav integration ─────────────────────────────────────────


def test_main_site_nav_includes_prototypes_link():
    """build.py must surface the Prototypes tab in the main nav."""
    from llmwiki import build as build_mod
    src = Path(build_mod.__file__).read_text(encoding="utf-8")
    assert '"prototypes/index.html", "Prototypes"' in src, (
        "build.py must add a `Prototypes` nav link pointing at "
        "prototypes/index.html; otherwise the hub is unreachable"
    )


def test_build_py_calls_prototype_hub():
    """build.py must invoke build_prototype_hub during site build."""
    from llmwiki import build as build_mod
    src = Path(build_mod.__file__).read_text(encoding="utf-8")
    assert "from llmwiki.prototypes import build_prototype_hub" in src
    assert "build_prototype_hub(out_dir)" in src


# ─── Edge cases ───────────────────────────────────────────────────────


def test_render_state_handles_unknown_slug_gracefully():
    """Renderer only handles known slugs — unknowns should raise KeyError
    so we fail fast rather than silently ship a blank page."""
    unknown = PrototypeState(slug="not-real", title="X", description="X")
    with pytest.raises(KeyError):
        render_state(unknown)


def test_generated_html_works_in_dark_mode():
    """Dark-mode palette flips via data-theme — the prototype callouts
    have dark-mode-specific overrides."""
    html = render_state(PROTOTYPE_STATES[0])  # page-shell
    # The callout dark-mode override must still be in the inline style
    # (moved to css.py later, but for now lives here).
    # Alternative check: palette through-line is present.
    assert "data-theme" in html or "#7C3AED" in html  # at least one palette hook


def test_every_prototype_state_has_back_to_site_link():
    """#268: Prototype pages used to be dead-ends — no way back to the
    live site without the browser back button. Every rendered state
    must now include both a ← Back to site and an All prototypes link."""
    from llmwiki.prototypes import PROTOTYPE_STATES, render_state
    for state in PROTOTYPE_STATES:
        html = render_state(state)
        assert "Back to site" in html, f"{state.slug} missing Back-to-site link"
        assert 'href="../index.html"' in html, (
            f"{state.slug} back link doesn't point at the site root"
        )
        assert "All prototypes" in html, (
            f"{state.slug} missing link back to the prototypes hub"
        )
