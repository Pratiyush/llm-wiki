"""#478 + #479: command palette + help dialog used `aria-hidden="true"`
as their visibility gate, which axe-core flags via the
`aria-hidden-focus` rule (focusable children of an aria-hidden ancestor
are unreachable to AT users). They also had no focus trap — Tab walked
behind into the page chrome — and ESC didn't return focus to the trigger.

The fix swaps the gate to a `.open` class and adds:
  - `inert` on every body sibling while a dialog is open
  - focus trap on Tab / Shift+Tab inside the dialog
  - focus restoration to the original trigger on close

These tests pin the markup, CSS, and JS contracts.
"""
from __future__ import annotations

from llmwiki.build import page_foot
from llmwiki.render.css import CSS
from llmwiki.render.js import JS


def _foot() -> str:
    return page_foot()


# ─── Markup contract ──────────────────────────────────────────────────


def test_palette_markup_no_longer_uses_aria_hidden() -> None:
    """The palette container must NOT carry `aria-hidden="true"` —
    that's the axe-core violation we're fixing."""
    foot = _foot()
    assert '<div id="palette" class="palette">' in foot
    assert 'id="palette" class="palette" aria-hidden="true"' not in foot


def test_help_dialog_markup_no_longer_uses_aria_hidden() -> None:
    foot = _foot()
    assert '<div id="help-dialog" class="help-dialog">' in foot
    assert 'id="help-dialog" class="help-dialog" aria-hidden="true"' not in foot


# ─── CSS contract ─────────────────────────────────────────────────────


def test_css_uses_open_class_for_palette_visibility() -> None:
    """Visibility now driven by `.open` — make sure the rule exists
    and the old `[aria-hidden="false"]` gate is gone."""
    assert ".palette.open { display: block; }" in CSS
    assert '.palette[aria-hidden="false"]' not in CSS


def test_css_uses_open_class_for_help_visibility() -> None:
    assert ".help-dialog.open { display: block; }" in CSS
    assert '.help-dialog[aria-hidden="false"]' not in CSS


# ─── JS contract — open / close + inert + focus restoration ───────────


def test_js_dialog_open_helper_uses_inert_and_class() -> None:
    """__openDialog must (a) flip the `.open` class, (b) set `inert`
    on body siblings, (c) capture the previous focused element."""
    assert "__openDialog" in JS
    assert 'classList.add("open")' in JS
    assert 'setAttribute("inert"' in JS
    assert "__dialogLastFocus = document.activeElement" in JS


def test_js_dialog_close_helper_restores_focus_and_clears_inert() -> None:
    """Close must (a) flip class off, (b) remove `inert` from siblings,
    (c) restore focus to the saved trigger."""
    assert "__closeDialog" in JS
    assert 'classList.remove("open")' in JS
    assert 'removeAttribute("inert")' in JS
    assert "__dialogLastFocus.focus()" in JS


def test_js_palette_uses_dialog_helpers() -> None:
    """Both open/close paths route through the shared helpers so the
    inert + focus contract is uniform across palette and help."""
    open_block = JS[JS.find("function openPalette()"): JS.find("function closePalette()")]
    close_block = JS[JS.find("function closePalette()"): JS.find("function openHelp()")]
    assert "__openDialog(p, input)" in open_block
    assert "__closeDialog(p)" in close_block


def test_js_help_uses_dialog_helpers() -> None:
    open_block = JS[JS.find("function openHelp()"): JS.find("function closeHelp()")]
    close_block = JS[JS.find("function closeHelp()"): JS.find("function closeHelp()") + 200]
    assert "__openDialog(d" in open_block
    assert "__closeDialog(d)" in close_block


# ─── JS contract — focus trap on Tab / Shift+Tab ──────────────────────


def test_js_traps_tab_inside_dialog() -> None:
    """A `__trapTab` helper must wrap focus inside the dialog so Tab
    can't walk behind into the inert page chrome."""
    assert "__trapTab" in JS
    # Wrapping logic — Shift+Tab from first goes to last; Tab from last
    # goes to first.
    assert "shiftKey && document.activeElement === first" in JS
    assert "!e.shiftKey && document.activeElement === last" in JS


def test_js_focusable_walker_skips_hidden_and_disabled() -> None:
    """The focusable-elements walk must exclude disabled inputs and
    hidden elements (offsetParent === null)."""
    block = JS[JS.find("__getFocusable"): JS.find("__openDialog")]
    assert "disabled" in block.lower()
    assert "offsetParent" in block


# ─── ESC handler updated to read the new state ────────────────────────


def test_esc_handler_uses_open_class_not_aria_hidden() -> None:
    """The Esc key handler used `getAttribute('aria-hidden') === 'false'`
    as the open-state check. Now reads the .open class."""
    assert 'p.classList.contains("open")' in JS
    assert 'h.classList.contains("open")' in JS
    # Make sure the old check is gone.
    assert 'getAttribute("aria-hidden") === "false"' not in JS
