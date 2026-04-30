# Playwright Test Agents bootstrap — paste-ready scaffold

This document is the **paste-ready scaffold** for #464 (bootstrap) and
#467 (healer-in-CI). When the operator approves the one-time Node
toolchain addition (per ADR-001's Constraints clause), every file
below ships verbatim and the epic closes in two PRs.

Why a paste-ready scaffold exists at all: the agent's own memory rule
("Node install gets denied") plus ADR-001 explicitly require explicit
operator authorization before any `npm install` can run in this repo.
This document captures the full bootstrap so the authorization step
is a 30-second paste, not a 30-minute interactive session.

---

## Prerequisites — what the operator approves

Approving #464 means consenting to:

| Change | Permanent? |
|---|---|
| `package.json` + `package-lock.json` at repo root | yes |
| Node devDependency: `@playwright/test` (~50 MB transitive) | yes |
| ~300 MB Chromium binary in `~/Library/Caches/ms-playwright/` | per-machine |
| New `tests/agents/` directory | yes |
| New `playwright.config.ts` | yes |
| New `.github/workflows/agents-e2e.yml` CI job | yes |

If any of those is a no, stop here and Path C (drop the agents
workflow entirely) is the right move — file an ADR-002 superseding
ADR-001.

---

## Step 1 — bootstrap commands

```bash
git checkout -b feat/464-playwright-agents-bootstrap
npm init -y

# Pin to a recent stable Playwright. Update yearly.
npm install -D @playwright/test@1.58.0

# One-time browser install (Chromium only — matches our pytest config).
npx playwright install chromium --with-deps
```

After the install, `package.json` looks roughly like:

```json
{
  "name": "llmwiki-playwright-agents",
  "private": true,
  "version": "0.0.0",
  "description": "TS Playwright Test Agents — gated by ADR-001.",
  "scripts": {
    "test": "playwright test",
    "test:headed": "playwright test --headed",
    "report": "playwright show-report"
  },
  "devDependencies": {
    "@playwright/test": "^1.58.0"
  }
}
```

Pin both `package.json` AND `package-lock.json` in git.

---

## Step 2 — `playwright.config.ts`

Drop this file at the repo root. It lays out the test directory under
`tests/agents/` (per ADR-001 Path A), points at `localhost:8765`
served by the existing build pipeline, and uploads HTML report +
traces on failure.

```typescript
import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.LLMWIKI_BASE_URL ?? "http://127.0.0.1:8765";

export default defineConfig({
  testDir: "tests/agents",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: [
    ["html", { open: "never", outputFolder: "playwright-report" }],
    ["list"],
  ],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    // ADR-001 Path A: chromium only initially. Adding firefox/webkit
    // is a #464 follow-up, not a blocker.
  ],
  webServer: {
    // We don't auto-build here — CI builds + serves before invoking
    // playwright test. Local dev: `python3 -m llmwiki build && python3
    // -m llmwiki serve` in another terminal first.
    command: "true",
    url: baseURL,
    reuseExistingServer: true,
    timeout: 30000,
  },
});
```

---

## Step 3 — seed test at `tests/agents/seed.spec.ts`

A minimal smoke test that proves the harness works against a built
demo site. Real specs come from #465 (already shipped under
`specs/*.md`) once the Generator agent runs.

```typescript
import { test, expect } from "@playwright/test";

test.describe("seed — site reachability", () => {
  test("home renders the LLM Wiki hero", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/LLM Wiki/);
    await expect(page.locator("h1").first()).toContainText("LLM Wiki");
  });

  test("nav has the canonical links", async ({ page }) => {
    await page.goto("/");
    for (const label of ["Home", "Projects", "Sessions", "Graph", "Docs", "Changelog"]) {
      await expect(page.getByRole("link", { name: label }).first()).toBeVisible();
    }
  });

  test("graph page carries the site nav (regression for #456)", async ({ page }) => {
    await page.goto("/graph.html");
    await expect(page.getByRole("link", { name: "Home" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Graph" }).first()).toBeVisible();
  });
});
```

---

## Step 4 — CI workflow at `.github/workflows/agents-e2e.yml`

```yaml
name: Playwright Test Agents (TS)

on:
  pull_request:
    paths:
      - "llmwiki/build.py"
      - "llmwiki/render/**"
      - "tests/agents/**"
      - "playwright.config.ts"
      - "package.json"
      - "package-lock.json"
  push:
    branches: [master]
    paths:
      - "llmwiki/build.py"
      - "llmwiki/render/**"
      - "tests/agents/**"
      - "playwright.config.ts"

permissions:
  contents: read

jobs:
  agents-e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"

      - name: Install Python deps
        run: pip install -e .

      - name: Install Node deps
        run: npm ci

      - name: Install Chromium for Playwright
        run: npx playwright install chromium --with-deps

      - name: Build the demo site
        run: |
          python3 -m llmwiki init
          python3 -m llmwiki build

      - name: Serve site in the background
        run: |
          python3 -m llmwiki serve --port 8765 &
          for i in {1..30}; do
            curl -fsS http://127.0.0.1:8765/ > /dev/null && break
            sleep 1
          done

      - name: Run Playwright Test Agents
        run: npx playwright test
        env:
          LLMWIKI_BASE_URL: http://127.0.0.1:8765

      - name: Upload HTML report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: agents-html-report
          path: playwright-report
          retention-days: 14

      - name: Upload traces
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: agents-traces
          path: test-results
          retention-days: 14
```

---

## Step 5 — `.gitignore` additions

```
# Playwright Test Agents (#464)
node_modules/
playwright-report/
test-results/
.playwright/
```

---

## Step 6 — `pyproject.toml` note (no functional change)

Add a comment near the `[e2e]` extra clarifying the dual-suite
arrangement:

```toml
# E2E test harness — Playwright drives a real browser + pytest-bdd
# turns Gherkin `.feature` files into pytest scenarios + pytest-html
# produces a browseable HTML report per run. Opt-in because
# Playwright installs ~300 MB of browsers per engine.
#
# As of #464 (v1.3.81), this Python suite is the GATING contract
# (per ADR-001). The TS Playwright Test Agents under tests/agents/
# are advisory until #467 ships; both run on every PR.
#
# Install with: `pip install -e '.[e2e]'` then `playwright install chromium`
```

---

## Step 7 — CHANGELOG entry for v1.3.81

```markdown
## [1.3.81] — <DATE>

#464 — Playwright Test Agents bootstrap (Path A from ADR-001).

### Added

- **`package.json` + `package-lock.json`** — Node toolchain for the
  TS Playwright runner. Pinned to `@playwright/test@1.58.0`. First
  Node deps in this repo; explicitly authorized by the operator per
  ADR-001's Constraints clause.
- **`playwright.config.ts`** — TS runner config; testDir
  `tests/agents/`, chromium-only project, HTML reporter, trace on
  retry, screenshot + video on failure.
- **`tests/agents/seed.spec.ts`** — three smoke scenarios (home
  renders, nav has canonical links, graph page carries nav as the
  regression lock for #456). Real generated specs land via #466's
  Generator pass once this bootstrap is on master.
- **`.github/workflows/agents-e2e.yml`** — runs `npx playwright
  test` on every PR touching `llmwiki/build.py`, `llmwiki/render/`,
  `tests/agents/`, or the playwright config. Builds the demo site,
  serves it on `localhost:8765`, runs Chromium scenarios, uploads
  HTML report (14-day retention) + traces (failure only).
- **`docs/maintainers/playwright-agents-bootstrap.md`** stays in
  the repo as the historical record of the bootstrap commands +
  config decisions.

### Changed

- `.gitignore` — added `node_modules/`, `playwright-report/`,
  `test-results/`, `.playwright/`.
- `pyproject.toml` — comment clarifying dual-suite arrangement
  per ADR-001 (Python suite is gating contract; TS suite is
  advisory).

### Constraints honored

- Path A (TS alongside Python) per ADR-001
- Chromium only initially (matches existing pytest-playwright config)
- Python `tests/e2e/` suite is **unchanged** and stays the gating
  contract until the Path-B deprecation trigger (≥80% TS coverage
  parity + ≥50% Healer-CI auto-patch acceptance for one release
  cycle) hits.
```

---

## #467 — healer-in-CI (separate PR after #464 lands)

The Healer agent watches the agents-e2e job. When a UI PR causes a
locator to drift (selector misses, timeout, etc.), the Healer
proposes a patched selector via PR comment.

The mechanism is:

1. The Healer's locator-update suggestions land in
   `playwright-report/` as part of the failed run's JSON output.
2. A second workflow (`agents-healer.yml`) reads that JSON, formats
   each suggestion as a PR review comment with a suggested-changes
   diff block GitHub's UI can apply with one click.

Workflow shell at `.github/workflows/agents-healer.yml`:

```yaml
name: Playwright Healer (auto-patch suggestions)

on:
  workflow_run:
    workflows: ["Playwright Test Agents (TS)"]
    types: [completed]

permissions:
  pull-requests: write
  contents: read
  actions: read

jobs:
  comment:
    if: github.event.workflow_run.conclusion == 'failure'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          run-id: ${{ github.event.workflow_run.id }}
          name: agents-html-report
          github-token: ${{ secrets.GITHUB_TOKEN }}
      - name: Extract Healer suggestions
        id: extract
        run: |
          # Healer writes locator-update suggestions to a JSON
          # alongside the HTML report; we transform each into a
          # GitHub suggested-changes comment.
          node scripts/healer-comment.js \
            --report playwright-report/results.json \
            --pr ${{ github.event.workflow_run.pull_requests[0].number }}
```

Plus a `scripts/healer-comment.js` (~80 LOC) that walks the
Playwright JSON report, finds locator-failure entries with
`healer.suggestedFix`, and posts each as a `gh pr comment` via the
GitHub Actions REST API.

This stays as a doc-only sketch until #464 ships — without the TS
runner there's no JSON report to extract from.

---

## Path-C escape

If after three full release cycles (per ADR-001 deprecation trigger)
either coverage parity stays under 80% or healer auto-patch
acceptance stays under 50%, file an ADR-002:

- delete `package.json`, `package-lock.json`, `playwright.config.ts`,
  `tests/agents/`, `.github/workflows/agents-e2e.yml`,
  `.github/workflows/agents-healer.yml`, `scripts/healer-comment.js`
- restore `.gitignore` to its pre-#464 state
- mark ADR-001 superseded by ADR-002
- the Python `tests/e2e/` suite continues unchanged

The Path-C escape is the reason this scaffold lives in `docs/`
rather than as a half-applied set of files: rolling back is one
`git rm` of the listed files, no test rewrite needed.
