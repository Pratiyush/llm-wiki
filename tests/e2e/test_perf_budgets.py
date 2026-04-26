"""#630 (#pw-x2): per-page performance budgets.

Captures `performance.timing.domContentLoadedEventEnd` and
`loadEventEnd` for each emitted page-type and asserts they're under
the per-page budget defined in `tests/perf-budgets.json`. Catches
bundle bloat + asset regressions that don't show up in static
analysis but degrade real-page perceived load.

Why these signals (not LCP/INP/CLS): the Web Vitals trio is more
faithful to user perception, but the captures fluctuate by ±200ms
on shared CI runners depending on noisy-neighbour load. DCL +
load are deterministic enough to catch regressions of ≥500ms
without flaking. We can graduate to LCP once baseline numbers
stabilise (tracked as a follow-up, not blocking on it).

The budgets file is intentionally conservative — set well above
the seeded build's actual numbers so flakiness doesn't drown the
real signal. Tighten via a deliberate baseline pass on the live
demo when we have one.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

BUDGETS_FILE = Path(__file__).parent.parent / "perf-budgets.json"


def _load_budgets() -> dict[str, dict[str, int]]:
    raw = json.loads(BUDGETS_FILE.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


BUDGETS = _load_budgets()


def _capture_timings(page: Page) -> dict[str, float]:
    """Return DCL + load times in ms relative to navigationStart."""
    return page.evaluate(
        """() => {
            const t = performance.timing;
            const start = t.navigationStart;
            return {
                dcl_ms: Math.round(t.domContentLoadedEventEnd - start),
                load_ms: Math.round(t.loadEventEnd - start),
            };
        }"""
    )


@pytest.mark.parametrize("path", list(BUDGETS.keys()))
def test_page_meets_perf_budget(page: Page, base_url: str, path: str) -> None:
    """Load the page, wait for `load`, capture timing, compare to
    the budget for that path. Skip cleanly when the page isn't
    shipped on this build (e.g. graph.html on an empty wiki)."""
    resp = page.request.get(f"{base_url}{path}")
    if resp.status >= 400:
        pytest.skip(f"{path} not shipped on this build (HTTP {resp.status})")

    page.goto(f"{base_url}{path}", wait_until="load")
    timings = _capture_timings(page)
    budget = BUDGETS[path]

    failures = []
    for metric in ("dcl_ms", "load_ms"):
        if timings[metric] > budget[metric]:
            failures.append(
                f"{metric} = {timings[metric]}ms > budget {budget[metric]}ms"
            )
    if failures:
        pytest.fail(
            f"{path} blew its perf budget:\n  "
            + "\n  ".join(failures)
            + f"\n  (timings={timings}, budget={budget})"
        )
