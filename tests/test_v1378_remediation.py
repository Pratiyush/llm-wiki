"""Regression tests for the v1.3.78 multi-agent-review remediation.

The 5-agent review on the v1.3.66 → v1.3.77 diff surfaced six HIGH
issues; this file pins the contracts each fix introduced so a future
PR can't silently regress them.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.adapters import (
    REGISTRY,
    REGISTRY_ALIASES,
    discover_adapters,
    discover_contrib,
    register,
    resolve_adapter_name,
)


# ─── Fix #1 — REGISTRY canonical-only; aliases live separately ───────


def test_registry_holds_only_canonical_names():
    """Aliases like `copilot-chat` must NOT be REGISTRY keys.

    Before this fix, `register(name, aliases=[...])` inserted every
    alias into REGISTRY directly, which made `cmd_adapters` print
    duplicate rows and made `adapter_status` look up the wrong config
    key on the alias row.
    """
    discover_adapters()
    discover_contrib(["copilot_chat", "copilot_cli"])
    for key, cls in REGISTRY.items():
        assert cls.name == key, (
            f"REGISTRY key {key!r} disagrees with cls.name {cls.name!r} — "
            "alias has leaked back into REGISTRY"
        )


def test_kebab_alias_resolves_via_registry_aliases():
    """The historical kebab-case names still resolve through the
    ALIASES map + the resolve_adapter_name helper."""
    discover_adapters()
    discover_contrib(["copilot_chat", "copilot_cli"])
    assert REGISTRY_ALIASES.get("copilot-chat") == "copilot_chat"
    assert REGISTRY_ALIASES.get("copilot-cli") == "copilot_cli"
    assert resolve_adapter_name("copilot-chat") == "copilot_chat"
    assert resolve_adapter_name("copilot-cli") == "copilot_cli"
    assert resolve_adapter_name("copilot_chat") == "copilot_chat"  # canonical
    assert resolve_adapter_name("does-not-exist") is None


def test_alias_collision_with_canonical_name_raises():
    """Defense-in-depth: an alias must not silently shadow an existing
    canonical adapter."""
    discover_adapters()  # ensures `claude_code` is registered

    class _DummyAdapter:
        pass

    with pytest.raises(ValueError, match="would shadow existing"):
        register("dummy_x", aliases=["claude_code"])(_DummyAdapter)


# ─── Fix #2 — build_site sibling-failure isolation ───────────────────


def test_build_site_sibling_failure_isolation_is_documented_in_source():
    """Static check on the build.py source: a per-source sibling-write
    failure must NOT short-circuit the loop. Spinning up the real
    build_site fixture is expensive; this lightweight check pins the
    code shape so the regression-causing pattern can't come back.

    The bad pattern: setting `siblings_failed = True` and then
    `continue`-ing in subsequent iterations on the strength of that
    flag. The good pattern: append to a `sibling_failures` list and
    let the loop keep running.
    """
    build_path = REPO_ROOT / "llmwiki" / "build.py"
    text = build_path.read_text(encoding="utf-8")

    # The new contract: there's a sibling_failures list (or equivalent
    # per-source-isolated structure) the loop appends to.
    assert "sibling_failures" in text, (
        "build.py no longer tracks per-source sibling failures in a list; "
        "the v1.3.78 regression isolation may have been removed"
    )
    # The pattern that caused the bug: a single flag + continue.
    bad_pattern = re.compile(
        r"if siblings_failed[^:]*:\s*\n\s*continue", re.MULTILINE
    )
    assert not bad_pattern.search(text), (
        "build.py still has `if siblings_failed: continue` inside the "
        "render loop — this is the contagion pattern v1.3.78 fixed"
    )


# ─── Fix #3 — cli.py imports at module top ──────────────────────────


def test_cli_module_has_no_E402_imports():
    """cli.py must not have `from llmwiki.X import Y` lines AFTER any
    `def ` or `class ` statement at module scope (PEP 8 E402).

    Underscore-prefixed re-export imports + `# noqa` lines are still
    OK as long as they're at the TOP of the file before any def/class.
    """
    cli_path = REPO_ROOT / "llmwiki" / "cli.py"
    lines = cli_path.read_text(encoding="utf-8").splitlines()

    # Find the line of the first top-level `def ` or `class `.
    first_def_line = None
    for i, line in enumerate(lines):
        if line.startswith("def ") or line.startswith("class "):
            first_def_line = i
            break

    assert first_def_line is not None, "cli.py has no def or class — unexpected"

    offending: list[tuple[int, str]] = []
    for i in range(first_def_line + 1, len(lines)):
        # Only top-level lines starting at column 0; function-internal
        # imports are indented and don't violate E402 in the same way.
        if not lines[i].startswith("from llmwiki."):
            continue
        offending.append((i + 1, lines[i]))

    assert not offending, (
        "cli.py has top-level `from llmwiki.X` imports after a def/class "
        f"statement (PEP 8 E402): {offending}"
    )


# ─── Fix #4 — timeline label uses textContent, not innerHTML ────────


def test_timeline_label_uses_textcontent_not_innerhtml():
    """The timeline-block builder must NOT interpolate `labelText` into
    `tl.innerHTML` — that's a future-XSS hazard. Verify the JS source
    builds a real text node."""
    js_path = REPO_ROOT / "llmwiki" / "render" / "js.py"
    text = js_path.read_text(encoding="utf-8")

    # The old pattern was: tl.innerHTML = '<div...>' + labelText + '</div>' + svg
    # The new pattern uses createElement + textContent.
    bad_pattern = re.compile(r"tl\.innerHTML\s*=\s*['\"][^'\"]*'\s*\+\s*labelText")
    assert not bad_pattern.search(text), (
        "render/js.py still concatenates labelText into innerHTML — that's "
        "the future-XSS gap the v1.3.78 review flagged. Use createElement + "
        "textContent for the label."
    )

    # The new pattern must include a textContent assignment for the label.
    assert "labelEl.textContent = labelText" in text


# ─── Fix #5 — nav-hamburger aria-label updates with state ──────────


def test_nav_hamburger_aria_label_toggles_with_state():
    """The hamburger setOpen() must update aria-label to mirror the
    drawer state — screen readers should hear "Close" when open."""
    js_path = REPO_ROOT / "llmwiki" / "render" / "js.py"
    text = js_path.read_text(encoding="utf-8")
    # Look for the dynamic aria-label inside setOpen.
    assert 'open ? "Close navigation menu" : "Open navigation menu"' in text


# ─── Fix #6 — theme button aria-label for tri-state ────────────────


def test_theme_toggle_uses_aria_label_for_tristate():
    """aria-pressed alone collapses the tri-state (system/dark/light)
    into binary — a screen reader user can't distinguish system from
    light. Verify aria-label is set dynamically too, on BOTH the
    desktop button and the mobile menu button."""
    js_path = REPO_ROOT / "llmwiki" / "render" / "js.py"
    text = js_path.read_text(encoding="utf-8")

    # Desktop and mobile both need to set aria-label dynamically.
    desktop_label = 'btn.setAttribute(\n        "aria-label",'
    mobile_label = 'themeBtn.setAttribute("aria-label",'
    assert desktop_label in text or 'btn.setAttribute("aria-label",' in text
    assert mobile_label in text


# ─── Fix #5 (CSS half) — forced-colors fallback ────────────────────


def test_nav_hamburger_has_forced_colors_fallback():
    """Windows High Contrast Mode (forced-colors) overrides our custom
    palette; without the fallback the hamburger button visually
    disappears."""
    css_path = REPO_ROOT / "llmwiki" / "render" / "css.py"
    text = css_path.read_text(encoding="utf-8")
    assert "@media (forced-colors: active)" in text
    assert ".nav-hamburger { border: 2px solid ButtonText; }" in text
