import { defineConfig, devices } from "@playwright/test";

// #464: TS Playwright Test Agents config (ADR-001 Path A).
// The Python tests/e2e/ suite is the gating contract; this TS suite
// is advisory until #467 healer-in-CI ships and the Path-B
// deprecation trigger is met (≥80% coverage parity + ≥50% healer
// auto-patch acceptance, sustained one release cycle).

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
    // #467 healer-in-CI: JSON report consumed by scripts/healer-comment.js
    // to post locator-update suggestions as PR comments on failure.
    ["json", { outputFile: "playwright-report/results.json" }],
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
    // chromium only initially — matches the existing pytest-playwright
    // config. firefox + webkit are a #464 follow-up, not a blocker.
  ],
  webServer: {
    // CI builds + serves before invoking `playwright test`; we don't
    // auto-build here. Local dev: run `python3 -m llmwiki build &&
    // python3 -m llmwiki serve` in another terminal first.
    command: "true",
    url: baseURL,
    reuseExistingServer: true,
    timeout: 30000,
  },
});
