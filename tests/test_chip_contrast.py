"""Tests for #480 — yellow chip contrast must meet WCAG AA.

The fix bumps light-mode `.fresh-yellow` text from `#b45309` to
`#92400e` so the chip color on its `#fef3c7` background passes the
4.5:1 normal-text threshold. Verified by computing the contrast
ratio with the W3C relative-luminance formula directly.
"""

from __future__ import annotations

import re

from llmwiki.render.css import CSS


# ─── W3C relative-luminance + contrast (no external deps) ──────────────


def _channel(c: int) -> float:
    """sRGB → linear-light per WCAG 2.x formula."""
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(hex_str: str) -> float:
    h = hex_str.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(fg_hex: str, bg_hex: str) -> float:
    l1, l2 = luminance(fg_hex), luminance(bg_hex)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


# ─── tests ─────────────────────────────────────────────────────────────


def test_fresh_yellow_chip_meets_aa_in_light_mode():
    """`.fresh-yellow { color: ...; background: #fef3c7 }` must hit ≥4.5:1."""
    m = re.search(
        r"\.fresh-yellow\s*\{\s*color:\s*(#[0-9a-fA-F]{6})\s*;\s*background:\s*(#[0-9a-fA-F]{6})",
        CSS,
    )
    assert m, "could not locate .fresh-yellow rule in CSS"
    fg, bg = m.group(1), m.group(2)
    ratio = contrast(fg, bg)
    assert ratio >= 4.5, (
        f".fresh-yellow contrast {ratio:.2f}:1 fails WCAG AA "
        f"(fg={fg}, bg={bg}). Bump fg darker."
    )


def test_token_ratio_tier_yellow_meets_aa_in_light_mode():
    """The other place yellow appears at non-trivial size — token tier values."""
    m = re.search(
        r"\.token-ratio-value\.tier-yellow\s*\{\s*color:\s*(#[0-9a-fA-F]{6})",
        CSS,
    )
    assert m, "could not locate .token-ratio-value.tier-yellow rule"
    fg = m.group(1)
    # Renders on white card backgrounds in this context.
    ratio = contrast(fg, "#ffffff")
    assert ratio >= 4.5, (
        f".token-ratio-value.tier-yellow contrast {ratio:.2f}:1 fails WCAG AA "
        f"(fg={fg} on white card)"
    )


def test_legacy_b45309_color_is_gone():
    """Regression guard: `#b45309` on light yellow chips was the bug."""
    # Pattern: yellow rule containing the legacy color
    legacy = re.search(
        r"\.fresh-yellow\s*\{\s*color:\s*#b45309",
        CSS,
        re.IGNORECASE,
    )
    assert legacy is None, (
        ".fresh-yellow still uses legacy #b45309 (4.49:1 contrast — fails AA)"
    )


def test_dark_mode_yellow_chip_unchanged_and_passes():
    """Sanity check: dark-mode variant wasn't broken by the fix."""
    m = re.search(
        r':root\[data-theme="dark"\]\s*\.fresh-yellow\s*\{\s*color:\s*(#[0-9a-fA-F]{6})\s*;\s*background:\s*(#[0-9a-fA-F]{6})',
        CSS,
    )
    assert m, "could not locate dark-mode .fresh-yellow rule"
    fg, bg = m.group(1), m.group(2)
    ratio = contrast(fg, bg)
    assert ratio >= 4.5, (
        f"dark .fresh-yellow contrast {ratio:.2f}:1 also broken "
        f"(fg={fg}, bg={bg}) — file separate ticket"
    )
