# theme-toggle spec (cross-cutting)

## Goal

Tri-state theme cycle that respects user choice across navigation and survives page reloads. Cycle: `system → dark → light → system`.

## URL pattern

- All pages — this is a cross-cutting concern, not a single page.

## Must

- The `#theme-toggle` button (desktop) and `#mbn-theme` button (mobile menu) BOTH cycle through the same tri-state sequence (closes the v1.3.67 mobile-button parity fix).
- Initial state with no `localStorage["llmwiki-theme"]` key respects the system `prefers-color-scheme` media query.
- Clicking the button when in "system" mode pins to "dark" and writes `localStorage["llmwiki-theme"] = "dark"`.
- Clicking again pins to "light" and writes `localStorage["llmwiki-theme"] = "light"`.
- Clicking again removes the key entirely, returning to "system".
- The HTML root `data-theme` attribute reflects the pinned state when pinned, and is **absent** when in system mode.
- Navigating from `/` to `/docs/` to `/graph.html` to `/sessions/` keeps the chosen theme — no reverts (closes #458).
- `aria-pressed` on the toggle button mirrors whether dark is currently active (true|false).
- Closing and reopening the tab reads the saved choice on first paint — no flash of wrong theme.

## Should

- The mobile menu's theme button is reachable via keyboard and announces its state to screen readers.
- The toggle's icon visually reflects the next state in the cycle (sun / moon / monitor).

## Won't

- Won't have a fourth state. System / dark / light is the full universe.
- Won't follow `prefers-color-scheme` changes after the user has explicitly pinned a value.

## Cross-references

- v1.3.67 (#679) — mobile theme button tri-state parity fix
- #458 (closed) — theme persistence across `/docs/` navigation
- `llmwiki/render/js.py:80` — desktop tri-state cycle reference implementation
- `tests/e2e/features/responsive.feature` — partial coverage today
