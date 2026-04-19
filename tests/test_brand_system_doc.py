"""Tests for docs/design/brand-system.md (v1.2.0 · #115).

The doc is the canonical reference for typography/palette/motion, so it
must stay aligned with the actual CSS tokens in ``llmwiki/render/css.py``.
If someone renames ``--accent`` or bumps ``--radius`` without updating
the doc, these tests fail and point at the drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.render.css import CSS


BRAND_DOC = REPO_ROOT / "docs" / "design" / "brand-system.md"


@pytest.fixture(scope="module")
def doc() -> str:
    assert BRAND_DOC.is_file(), (
        "docs/design/brand-system.md missing — #115 landed it as the brand "
        "source of truth; re-create it rather than inlining values in code"
    )
    return BRAND_DOC.read_text(encoding="utf-8")


# ─── Structure ────────────────────────────────────────────────────────


def test_doc_has_all_core_sections(doc: str):
    for section in (
        "Typography", "Color palette", "Elevation",
        "Motion", "Spacing", "Export consistency",
    ):
        assert section in doc, f"brand doc missing section '{section}'"


def test_doc_mentions_light_and_dark_modes(doc: str):
    assert "Light mode" in doc
    assert "Dark mode" in doc


# ─── Palette tokens must match css.py ──────────────────────────────────


def _token_values(css: str, token: str) -> list[str]:
    """Return every value assigned to the token (light, dark, prefers-*)."""
    return re.findall(rf"^\s*{re.escape(token)}:\s*([^;]+);", css, re.MULTILINE)


PALETTE_TOKENS_IN_DOC = [
    "--bg",
    "--bg-alt",
    "--bg-card",
    "--bg-code",
    "--text",
    "--text-secondary",
    "--text-muted",
    "--border",
    "--border-subtle",
    "--accent",
    "--accent-light",
    "--accent-bg",
    "--radius",
    "--font",
    "--mono",
]


@pytest.mark.parametrize("token", PALETTE_TOKENS_IN_DOC)
def test_doc_references_every_core_token(doc: str, token: str):
    # Backticked in markdown
    assert f"`{token}`" in doc, (
        f"brand doc should document `{token}` (defined in llmwiki/render/css.py)"
    )


ACCENT_HEX = "#7C3AED"


def test_accent_hex_is_in_both_css_and_doc(doc: str):
    # Brand through-line: the purple #7C3AED must appear in the CSS and
    # the doc must call it out as the single accent color.
    assert ACCENT_HEX in CSS, "css.py lost the canonical --accent hex"
    # Case-insensitive because markdown tables sometimes lowercase
    assert ACCENT_HEX.lower() in doc.lower(), (
        "brand doc should cite the canonical accent hex #7C3AED"
    )


# ─── Typography ────────────────────────────────────────────────────────


def test_doc_names_canonical_typefaces(doc: str):
    assert "Inter" in doc
    assert "JetBrains Mono" in doc


def test_css_keeps_inter_and_jetbrains_mono():
    # If we ever silently swap typefaces, the doc will lie. This test
    # keeps the source-of-truth in sync.
    font_values = _token_values(CSS, "--font")
    mono_values = _token_values(CSS, "--mono")
    assert font_values, "css.py has no --font declaration"
    assert mono_values, "css.py has no --mono declaration"
    assert any("Inter" in v for v in font_values), (
        "css.py --font no longer includes Inter; update the brand doc "
        "or restore the token"
    )
    assert any("JetBrains Mono" in v for v in mono_values)


# ─── Motion ────────────────────────────────────────────────────────────


def test_doc_mentions_reduced_motion(doc: str):
    # Accessibility requirement — the doc must call out that we respect
    # `prefers-reduced-motion`.
    assert "prefers-reduced-motion" in doc


def test_css_still_honours_reduced_motion():
    assert "prefers-reduced-motion" in CSS, (
        "css.py dropped the prefers-reduced-motion guard — add it back "
        "or update the brand doc's motion rules"
    )


# ─── Radius ────────────────────────────────────────────────────────────


RADIUS_IN_DOC = re.compile(r"`--radius`[^|]*\|\s*`?(\d+)px`?")


def test_radius_value_in_doc_matches_css(doc: str):
    # Find the radius row in the "Elevation + radius" table.
    m = RADIUS_IN_DOC.search(doc)
    assert m, "brand doc should state the --radius value in pixels"
    doc_px = int(m.group(1))

    css_values = _token_values(CSS, "--radius")
    assert css_values, "css.py has no --radius token"
    css_px = int(re.match(r"\s*(\d+)px", css_values[0]).group(1))  # type: ignore[union-attr]
    assert doc_px == css_px, (
        f"brand doc says --radius is {doc_px}px but css.py says {css_px}px"
    )


# ─── Do/don't rules are present ───────────────────────────────────────


def test_doc_has_do_dont_section(doc: str):
    assert "Do / don't" in doc or "Do / don" in doc
    # Basic anchors for the two lists
    assert "**Do**" in doc
    assert "**Don't**" in doc


# ─── Cross-links ──────────────────────────────────────────────────────


def test_doc_links_to_css_source(doc: str):
    # The whole point is "tokens live in css.py, this is a mirror" —
    # make sure the link is there for drift investigation.
    assert "llmwiki/render/css.py" in doc
