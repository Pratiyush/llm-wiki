"""#459: WCAG 2.1 AA contrast guard for both light and dark themes.

The reported issue was visual — multiple text/background pairs on the
emitted site looked low-contrast. Auditing the agent badges revealed
real failures in the light theme:

  agent-cursor:   2.86:1 on light  (FAIL — needs 4.5:1)
  agent-codex:    3.33:1 on light  (FAIL)
  agent-gemini:   4.13:1 on light  (FAIL)
  agent-copilot:  4.49:1 on light  (FAIL — borderline)

The fix darkens those four light-theme text colors. These tests pin
the contrast contract for the surfaces the issue called out, computed
from the literal colors in `llmwiki/render/css.py` rather than running
axe-core in a browser. axe-core in CI is the right tool for an end-to-
end pass; this unit test is the per-commit guard so a CSS edit can't
regress contrast silently.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki.render.css import CSS

# WCAG 2.1 AA threshold for normal text (≥18pt or ≥14pt bold qualifies
# as "large" and only needs 3:1).
AA_NORMAL = 4.5
AA_LARGE = 3.0


# ─── Pure WCAG math, no deps ──────────────────────────────────────────


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rel_lum(rgb: tuple[int, int, int]) -> float:
    def _ch(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _ch(r) + 0.7152 * _ch(g) + 0.0722 * _ch(b)


def _contrast(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    fl, bl = _rel_lum(fg), _rel_lum(bg)
    lo, hi = min(fl, bl), max(fl, bl)
    return (hi + 0.05) / (lo + 0.05)


def _alpha_blend(
    fg_rgba: tuple[int, int, int, float],
    bg_rgb: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Composite an `rgba(...)` color over a solid background — what
    the browser actually renders for an `rgba()` background fill."""
    r, g, b, a = fg_rgba
    br, bg, bb = bg_rgb
    return (
        round(r * a + br * (1 - a)),
        round(g * a + bg * (1 - a)),
        round(b * a + bb * (1 - a)),
    )


# ─── Theme palette pulled from CSS ────────────────────────────────────


def _css_var(theme: str, name: str) -> str:
    """Read a `--var: #hex;` from the appropriate :root block in CSS."""
    if theme == "light":
        # The first :root block is light; second is dark via [data-theme="dark"].
        block_match = re.search(r":root\s*\{(.*?)\}", CSS, re.DOTALL)
    else:
        block_match = re.search(
            r':root\[data-theme="dark"\]\s*\{(.*?)\}', CSS, re.DOTALL
        )
    assert block_match, f"could not find :root block for theme {theme!r}"
    var_match = re.search(rf"{re.escape(name)}\s*:\s*(#[0-9a-fA-F]{{3,8}})", block_match.group(1))
    assert var_match, f"variable {name!r} not found in {theme} :root"
    return var_match.group(1)


# ─── Static text-on-bg pairs (the most prominent surfaces) ────────────


PAIRS = [
    # (theme, fg_var, bg_var, threshold, label)
    ("light", "--text", "--bg", AA_NORMAL, "body text on bg"),
    ("light", "--text-secondary", "--bg", AA_NORMAL, "secondary text on bg"),
    ("light", "--text-muted", "--bg", AA_NORMAL, "muted text on bg"),
    ("light", "--text-muted", "--bg-alt", AA_NORMAL, "muted text on bg-alt"),
    ("light", "--accent", "--bg", AA_NORMAL, "accent on bg"),
    ("light", "--accent", "--bg-card", AA_NORMAL, "accent on bg-card"),
    ("dark", "--text", "--bg", AA_NORMAL, "body text on bg"),
    ("dark", "--text-secondary", "--bg", AA_NORMAL, "secondary text on bg"),
    ("dark", "--text-muted", "--bg", AA_NORMAL, "muted text on bg"),
    ("dark", "--text-muted", "--bg-card", AA_NORMAL, "muted text on bg-card"),
    ("dark", "--accent", "--bg", AA_NORMAL, "accent on bg"),
    ("dark", "--accent", "--bg-card", AA_NORMAL, "accent on bg-card"),
]


@pytest.mark.parametrize("theme,fg_var,bg_var,thresh,label", PAIRS)
def test_palette_pair_meets_wcag_aa(
    theme: str, fg_var: str, bg_var: str, thresh: float, label: str
) -> None:
    fg = _hex_to_rgb(_css_var(theme, fg_var))
    bg = _hex_to_rgb(_css_var(theme, bg_var))
    ratio = _contrast(fg, bg)
    assert ratio >= thresh, (
        f"{theme}/{label}: contrast {ratio:.2f}:1 below WCAG AA "
        f"threshold {thresh}:1 ({fg_var} on {bg_var})"
    )


# ─── Agent badge contrast (alpha-blended bg over page bg) ─────────────


# Each agent badge in CSS has the shape:
#   .agent-X   { color: #FG; background: rgba(R,G,B,0.10); border-color: ... }
# The badge sits directly on the page bg (--bg), so the effective bg is
# the alpha-blend of the rgba over white (light) or near-black (dark).
AGENT_BADGES_LIGHT = {
    # name           fg hex      bg rgba (R,G,B,a)
    "agent-claude":  ("#7C3AED", (124, 58, 237, 0.10)),
    "agent-codex":   ("#047857", (5, 150, 105, 0.10)),
    "agent-copilot": ("#1E40AF", (37, 99, 235, 0.10)),
    "agent-cursor":  ("#92400E", (217, 119, 6, 0.10)),
    "agent-gemini":  ("#991B1B", (220, 38, 38, 0.10)),
}
AGENT_BADGES_DARK = {
    "agent-claude":  ("#A78BFA", (167, 139, 250, 0.15)),
    "agent-codex":   ("#34D399", (52, 211, 153, 0.15)),
    "agent-copilot": ("#60A5FA", (96, 165, 250, 0.15)),
    "agent-cursor":  ("#FBBF24", (251, 191, 36, 0.15)),
    "agent-gemini":  ("#F87171", (248, 113, 113, 0.15)),
}


@pytest.mark.parametrize("name,colors", list(AGENT_BADGES_LIGHT.items()))
def test_agent_badge_light_meets_aa(name: str, colors: tuple[str, tuple[int, int, int, float]]) -> None:
    fg_hex, bg_rgba = colors
    page_bg = _hex_to_rgb(_css_var("light", "--bg"))
    eff_bg = _alpha_blend(bg_rgba, page_bg)
    ratio = _contrast(_hex_to_rgb(fg_hex), eff_bg)
    assert ratio >= AA_NORMAL, (
        f"{name} (light): contrast {ratio:.2f}:1 < {AA_NORMAL}:1 — "
        f"text {fg_hex} on effective bg rgb{eff_bg}"
    )


@pytest.mark.parametrize("name,colors", list(AGENT_BADGES_DARK.items()))
def test_agent_badge_dark_meets_aa(name: str, colors: tuple[str, tuple[int, int, int, float]]) -> None:
    fg_hex, bg_rgba = colors
    page_bg = _hex_to_rgb(_css_var("dark", "--bg"))
    eff_bg = _alpha_blend(bg_rgba, page_bg)
    ratio = _contrast(_hex_to_rgb(fg_hex), eff_bg)
    assert ratio >= AA_NORMAL, (
        f"{name} (dark): contrast {ratio:.2f}:1 < {AA_NORMAL}:1 — "
        f"text {fg_hex} on effective bg rgb{eff_bg}"
    )


# ─── Freshness chip contrast ──────────────────────────────────────────

FRESH_LIGHT = [
    ("fresh-green", "#15803d", "#dcfce7"),
    ("fresh-yellow", "#92400e", "#fef3c7"),
    ("fresh-red", "#b91c1c", "#fee2e2"),
]
FRESH_DARK = [
    ("fresh-green", "#86efac", "#052e16"),
    ("fresh-yellow", "#fcd34d", "#3a2a06"),
    ("fresh-red", "#fca5a5", "#3a0a0a"),
]


@pytest.mark.parametrize("name,fg,bg", FRESH_LIGHT)
def test_freshness_chip_light_meets_aa(name: str, fg: str, bg: str) -> None:
    ratio = _contrast(_hex_to_rgb(fg), _hex_to_rgb(bg))
    assert ratio >= AA_NORMAL, (
        f"{name} (light): contrast {ratio:.2f}:1 < {AA_NORMAL}:1"
    )


@pytest.mark.parametrize("name,fg,bg", FRESH_DARK)
def test_freshness_chip_dark_meets_aa(name: str, fg: str, bg: str) -> None:
    ratio = _contrast(_hex_to_rgb(fg), _hex_to_rgb(bg))
    assert ratio >= AA_NORMAL, (
        f"{name} (dark): contrast {ratio:.2f}:1 < {AA_NORMAL}:1"
    )
