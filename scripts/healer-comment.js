#!/usr/bin/env node
// scripts/healer-comment.js
// #467 healer-in-CI: parse a Playwright JSON results file, find every
// locator-failure entry, and post each as a PR review comment with a
// suggested-changes diff block GitHub's UI can apply with one click.
//
// Invoked by .github/workflows/agents-healer.yml after the
// agents-e2e workflow fails.
//
// Inputs (env):
//   GITHUB_TOKEN       — token with `pull-requests: write`
//   GITHUB_REPOSITORY  — owner/repo
//   PR_NUMBER          — pull request number
//   REPORT_PATH        — path to playwright-report/results.json
//
// Exit codes:
//   0 — comments posted (or zero suggestions)
//   1 — report missing or malformed JSON
//   2 — at least one comment POST failed

"use strict";

const fs = require("fs");
const https = require("https");

function fail(code, msg) {
  process.stderr.write(`healer-comment: ${msg}\n`);
  process.exit(code);
}

function parseReport(path) {
  if (!fs.existsSync(path)) {
    fail(1, `report not found at ${path}`);
  }
  const raw = fs.readFileSync(path, "utf-8");
  try {
    return JSON.parse(raw);
  } catch (e) {
    fail(1, `report is not valid JSON: ${e.message}`);
  }
}

// Walk the Playwright JSON tree, returning every test that failed
// with what looks like a locator error. Playwright's JSON shape:
//
// {
//   "suites": [
//     {
//       "title": "...",
//       "specs": [
//         {
//           "title": "...",
//           "file": "tests/agents/seed.spec.ts",
//           "tests": [
//             {
//               "results": [
//                 {
//                   "status": "failed",
//                   "error": { "message": "...", "stack": "..." },
//                   "errorLocation": { "file": "...", "line": N, "column": N }
//                 }
//               ]
//             }
//           ]
//         }
//       ]
//     }
//   ]
// }
function collectLocatorFailures(report) {
  const out = [];
  function walk(suite) {
    for (const spec of suite.specs || []) {
      for (const t of spec.tests || []) {
        for (const r of t.results || []) {
          if (r.status !== "failed") continue;
          const msg = (r.error && r.error.message) || "";
          // Heuristic: locator-related errors mention "locator", "selector",
          // "Timeout", or "did not match". Skip assertion-only fails.
          if (!/locator|selector|did not match|Timed? ?out/i.test(msg)) continue;
          out.push({
            file: spec.file || (r.errorLocation && r.errorLocation.file),
            line: (r.errorLocation && r.errorLocation.line) || 1,
            specTitle: spec.title,
            error: msg,
            suggestedFix: extractSuggestion(msg),
          });
        }
      }
    }
    for (const child of suite.suites || []) walk(child);
  }
  for (const top of report.suites || []) walk(top);
  return out;
}

// Pull a suggested locator out of the error message if Playwright's
// trace includes one. Real Healer integration would feed the failure
// to a model; the v1 implementation matches "use locator(...)"
// suggestions Playwright already prints.
function extractSuggestion(msg) {
  const m = msg.match(/use locator\((['"`])(.+?)\1\)/i);
  if (m) return { kind: "locator", value: m[2] };
  const sel = msg.match(/locator\((['"`])(.+?)\1\)/i);
  if (sel) return { kind: "current", value: sel[2] };
  return null;
}

function commentBody(failure) {
  const lines = [];
  lines.push("**Playwright Healer suggestion** — locator drift detected.");
  lines.push("");
  lines.push(`Test: \`${failure.specTitle}\``);
  lines.push("");
  lines.push("Error:");
  lines.push("```");
  lines.push(failure.error.split("\n").slice(0, 6).join("\n"));
  lines.push("```");
  if (failure.suggestedFix && failure.suggestedFix.kind === "locator") {
    lines.push("");
    lines.push("Suggested locator update:");
    lines.push("```suggestion");
    lines.push(`  await page.locator(${JSON.stringify(failure.suggestedFix.value)}).click();`);
    lines.push("```");
  } else {
    lines.push("");
    lines.push("_Healer could not extract a single suggested locator from the error._");
    lines.push("Inspect the trace artifact in the `Playwright Test Agents (TS)` job and update by hand.");
  }
  lines.push("");
  lines.push("<sub>Posted by `scripts/healer-comment.js` (#467). The TS agents suite is advisory per [ADR-001](../../docs/maintainers/ADR-001-playwright-stack.md) until the Path-B deprecation trigger hits.</sub>");
  return lines.join("\n");
}

function postComment(repo, pr, body, token) {
  return new Promise((resolve, reject) => {
    const [owner, name] = repo.split("/");
    const data = JSON.stringify({ body });
    const req = https.request(
      {
        hostname: "api.github.com",
        path: `/repos/${owner}/${name}/issues/${pr}/comments`,
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Accept": "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "llmwiki-healer-bot",
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(data),
        },
      },
      (res) => {
        let body = "";
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(JSON.parse(body));
          } else {
            reject(new Error(`POST returned ${res.statusCode}: ${body}`));
          }
        });
      },
    );
    req.on("error", reject);
    req.write(data);
    req.end();
  });
}

async function main() {
  // --check <path>: print what the script WOULD post without actually
  // calling the GitHub API. Used by tests/test_healer_comment.py to
  // pin the parsing contract without exercising the network.
  const checkIdx = process.argv.indexOf("--check");
  if (checkIdx !== -1) {
    const reportPath = process.argv[checkIdx + 1] || "playwright-report/results.json";
    const report = parseReport(reportPath);
    const failures = collectLocatorFailures(report);
    process.stdout.write(JSON.stringify({ count: failures.length, failures }, null, 2) + "\n");
    return;
  }

  const reportPath = process.env.REPORT_PATH || "playwright-report/results.json";
  const repo = process.env.GITHUB_REPOSITORY;
  const pr = process.env.PR_NUMBER;
  const token = process.env.GITHUB_TOKEN;

  if (!repo || !pr || !token) {
    fail(1, "missing GITHUB_REPOSITORY / PR_NUMBER / GITHUB_TOKEN env");
  }

  const report = parseReport(reportPath);
  const failures = collectLocatorFailures(report);
  if (failures.length === 0) {
    process.stdout.write("healer-comment: no locator failures found\n");
    return;
  }

  // Coalesce: post one comment per unique (file, line, specTitle) so a
  // flaky test that fails multiple times doesn't spam the PR.
  const seen = new Set();
  const unique = failures.filter((f) => {
    const k = `${f.file}:${f.line}:${f.specTitle}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });

  let failed = 0;
  for (const f of unique) {
    try {
      await postComment(repo, pr, commentBody(f), token);
      process.stdout.write(`healer-comment: posted for ${f.specTitle}\n`);
    } catch (e) {
      failed += 1;
      process.stderr.write(`healer-comment: POST failed for ${f.specTitle}: ${e.message}\n`);
    }
  }
  if (failed > 0) process.exit(2);
}

main().catch((e) => fail(1, e.message));
