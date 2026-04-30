"""Regression tests for scripts/healer-comment.js (#467).

Pins the parsing contract — the script's `collectLocatorFailures` +
`extractSuggestion` logic should:
- skip non-failed results
- skip failed results that aren't locator-related (e.g. plain assertion fails)
- extract a "use locator(...)" suggestion from Playwright's stack
- coalesce duplicates (same file:line:title) so a flaky test doesn't spam comments

The script ships with a `--check <path>` mode that prints the failures
JSON without calling the GitHub API; this test exercises that path.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT


HEALER = REPO_ROOT / "scripts" / "healer-comment.js"


def _run_check(report: dict, tmp_path: Path) -> dict:
    """Drop a report into tmp_path and run the script in --check mode."""
    p = tmp_path / "results.json"
    p.write_text(json.dumps(report), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(HEALER), "--check", str(p)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"script failed: {proc.stderr}"
    return json.loads(proc.stdout)


@pytest.fixture(autouse=True)
def _require_node():
    """Skip the suite if node isn't on PATH (e.g. on a contributor box
    that hasn't approved the #464 Node toolchain yet)."""
    if shutil.which("node") is None:
        pytest.skip("node not installed; healer script is Node")


def test_no_failures_returns_zero(tmp_path):
    report = {"suites": []}
    result = _run_check(report, tmp_path)
    assert result["count"] == 0
    assert result["failures"] == []


def test_passing_results_ignored(tmp_path):
    report = {
        "suites": [{
            "title": "smoke",
            "specs": [{
                "title": "home renders",
                "file": "tests/agents/seed.spec.ts",
                "tests": [{"results": [{"status": "passed"}]}],
            }],
        }],
    }
    result = _run_check(report, tmp_path)
    assert result["count"] == 0


def test_locator_timeout_collected(tmp_path):
    report = {
        "suites": [{
            "title": "smoke",
            "specs": [{
                "title": "graph nav present",
                "file": "tests/agents/seed.spec.ts",
                "tests": [{"results": [{
                    "status": "failed",
                    "error": {"message": "Timed out waiting for locator('#nav-graph')"},
                    "errorLocation": {"file": "tests/agents/seed.spec.ts", "line": 24},
                }]}],
            }],
        }],
    }
    result = _run_check(report, tmp_path)
    assert result["count"] == 1
    f = result["failures"][0]
    assert f["specTitle"] == "graph nav present"
    assert f["line"] == 24
    assert "Timed out" in f["error"]


def test_assertion_failure_ignored(tmp_path):
    """Plain expect(x).toBe(y) failures aren't locator drift — should
    be skipped so the healer doesn't comment on every assertion change."""
    report = {
        "suites": [{
            "title": "smoke",
            "specs": [{
                "title": "title check",
                "file": "tests/agents/seed.spec.ts",
                "tests": [{"results": [{
                    "status": "failed",
                    "error": {"message": "Expected: 'LLM Wiki'\n  Received: 'LLM Notebook'"},
                }]}],
            }],
        }],
    }
    result = _run_check(report, tmp_path)
    assert result["count"] == 0


def test_suggested_locator_extracted(tmp_path):
    """Playwright sometimes prints `use locator('foo')` in its hint —
    the script should surface that as suggestedFix.kind=='locator'."""
    report = {
        "suites": [{
            "title": "smoke",
            "specs": [{
                "title": "nav has Graph",
                "file": "tests/agents/seed.spec.ts",
                "tests": [{"results": [{
                    "status": "failed",
                    "error": {"message": "locator did not match.\n  Hint: use locator('a:has-text(\"Graph\")')"},
                }]}],
            }],
        }],
    }
    result = _run_check(report, tmp_path)
    assert result["count"] == 1
    fix = result["failures"][0]["suggestedFix"]
    assert fix is not None
    assert fix["kind"] == "locator"
    assert fix["value"] == 'a:has-text("Graph")'


def test_nested_suites_walked(tmp_path):
    """Playwright nests suites for describe-blocks; the walker must
    recurse to find failures inside child suites."""
    report = {
        "suites": [{
            "title": "outer",
            "specs": [],
            "suites": [{
                "title": "inner",
                "specs": [{
                    "title": "deep failure",
                    "file": "tests/agents/seed.spec.ts",
                    "tests": [{"results": [{
                        "status": "failed",
                        "error": {"message": "locator timed out"},
                    }]}],
                }],
            }],
        }],
    }
    result = _run_check(report, tmp_path)
    assert result["count"] == 1
    assert result["failures"][0]["specTitle"] == "deep failure"


def test_missing_report_exits_with_error(tmp_path):
    proc = subprocess.run(
        ["node", str(HEALER), "--check", str(tmp_path / "nope.json")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "report not found" in proc.stderr


def test_invalid_json_exits_with_error(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("not valid json {{{", encoding="utf-8")
    proc = subprocess.run(
        ["node", str(HEALER), "--check", str(p)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "not valid JSON" in proc.stderr
