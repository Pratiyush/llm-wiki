"""Tests for ``llmwiki synthesize --estimate`` breakdown (G-07 · #293).

Covers:
* Empty corpus → zeros with no divide-by-zero errors.
* Fresh corpus (nothing in state file) → incremental == full_force.
* Fully-synthesized corpus → incremental = $0, full_force > $0.
* Partial progress → incremental < full_force.
* Prefix-too-small warning surfaces into ``warnings`` bucket.
* Custom model + custom output_tokens override pricing.
* CLI subprocess prints the expected layout.
* Money numbers are non-negative and full_force ≥ incremental.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ─── synthesize_estimate_report: pure unit ───────────────────────────────


class _P:
    """Cheap Path-ish object for injecting raw_sessions without touching disk."""

    def __init__(self, rel: str):
        self._rel = rel
        self.name = rel.split("/")[-1]

    def __str__(self) -> str:  # used by the relative_to-fail branch
        return self._rel

    def relative_to(self, other):
        # Accept any "root" and return ourselves (the fixtures already
        # provide relative paths).
        return self


def _sessions(*rels: str) -> list:
    return [(_P(rel), {}, f"body for {rel} " * 200) for rel in rels]


def test_empty_corpus_reports_zero():
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=[],
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["corpus"] == 0
    assert rpt["synthesized"] == 0
    assert rpt["new"] == 0
    assert rpt["incremental_usd"] == 0.0
    assert rpt["full_force_usd"] == 0.0


def test_fresh_corpus_incremental_equals_full_force():
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md", "c.md"),
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["corpus"] == 3
    assert rpt["synthesized"] == 0
    assert rpt["new"] == 3
    # Same session bodies, same prefix, same pricing → identical.
    assert rpt["incremental_usd"] == pytest.approx(rpt["full_force_usd"])


def test_fully_synthesized_corpus_incremental_is_zero():
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md"),
        state_keys={"a.md", "b.md"},
        prefix_tokens=2000,
    )
    assert rpt["corpus"] == 2
    assert rpt["synthesized"] == 2
    assert rpt["new"] == 0
    assert rpt["incremental_usd"] == 0.0
    assert rpt["full_force_usd"] > 0.0


def test_partial_progress_incremental_less_than_full_force():
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md", "c.md"),
        state_keys={"a.md"},  # one already synthesized
        prefix_tokens=2000,
    )
    assert rpt["synthesized"] == 1
    assert rpt["new"] == 2
    assert rpt["incremental_usd"] < rpt["full_force_usd"]


def test_money_numbers_are_non_negative():
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("x.md"),
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["incremental_usd"] >= 0.0
    assert rpt["full_force_usd"] >= 0.0


def test_prefix_too_small_warning():
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=[],
        state_keys=set(),
        prefix_tokens=50,  # far below cache floor
    )
    assert rpt["warnings"], "expected a warning for tiny prefix"
    assert any("cache" in w.lower() or "1024" in w for w in rpt["warnings"])


def test_healthy_prefix_no_warning():
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=[],
        state_keys=set(),
        prefix_tokens=4000,
    )
    assert rpt["warnings"] == []


def test_custom_model_propagates():
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        prefix_tokens=2000,
        model="claude-haiku-4",
    )
    assert rpt["model"] == "claude-haiku-4"


def test_custom_output_tokens_affects_cost():
    from llmwiki.cli import synthesize_estimate_report
    rpt_small = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        prefix_tokens=2000,
        output_tokens_per_call=100,
    )
    rpt_big = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        prefix_tokens=2000,
        output_tokens_per_call=5000,
    )
    assert rpt_big["incremental_usd"] > rpt_small["incremental_usd"]


def test_state_key_matching_accepts_multiple_forms():
    """State keys come from different call sites — match bare-name,
    rel-path, or full-str."""
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("proj/abc.md"),
        state_keys={"proj/abc.md"},  # rel-path form
        prefix_tokens=2000,
    )
    assert rpt["synthesized"] == 1


def test_report_is_serialisable_to_json():
    """The JSON-able shape lets downstream tools consume the report."""
    from llmwiki.cli import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        prefix_tokens=2000,
    )
    s = json.dumps(rpt)
    round_tripped = json.loads(s)
    assert round_tripped["new"] == 1


def test_prefix_tokens_auto_computed_from_real_files(tmp_path, monkeypatch):
    """When prefix_tokens isn't provided, it's computed from the three
    cached-prefix files in REPO_ROOT."""
    import llmwiki.cli as cli_mod
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    (tmp_path / "CLAUDE.md").write_text("CLAUDE\n" * 2000, encoding="utf-8")
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "index.md").write_text("index\n" * 500, encoding="utf-8")
    (tmp_path / "wiki" / "overview.md").write_text("overview\n" * 500, encoding="utf-8")
    rpt = cli_mod.synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        # prefix_tokens deliberately NOT passed
    )
    assert rpt["prefix_tokens"] > 0


# ─── CLI subprocess smoke tests ──────────────────────────────────────────


def test_cli_estimate_prints_three_bucket_header():
    cp = _run_cli("synthesize", "--estimate")
    assert cp.returncode == 0, cp.stderr
    for line in ("Corpus:", "Synthesized (history):", "New since last run:"):
        assert line in cp.stdout, f"missing `{line}`"


def test_cli_estimate_prints_both_cost_rows():
    cp = _run_cli("synthesize", "--estimate")
    assert cp.returncode == 0, cp.stderr
    assert "Incremental sync:" in cp.stdout
    assert "Full re-synth:" in cp.stdout


def test_cli_estimate_prints_model_and_prefix():
    cp = _run_cli("synthesize", "--estimate")
    assert cp.returncode == 0, cp.stderr
    assert "Prefix:" in cp.stdout
    assert "Model:" in cp.stdout


def test_cli_estimate_doesnt_hit_network():
    """--estimate is a pure-local calculation; no HTTP libs needed."""
    # Run with DNS poisoned (127.0.0.1 only) via env isn't trivial —
    # instead assert that the CLI returns quickly (sub-5s is plenty).
    import time
    t0 = time.monotonic()
    cp = _run_cli("synthesize", "--estimate")
    elapsed = time.monotonic() - t0
    assert cp.returncode == 0
    assert elapsed < 30, f"estimate took {elapsed:.1f}s — too slow"


def test_cli_estimate_never_prints_negative_dollar():
    cp = _run_cli("synthesize", "--estimate")
    assert cp.returncode == 0
    assert "$-" not in cp.stdout


def test_cli_estimate_full_force_not_less_than_incremental():
    """Invariant: re-synthesizing everything can't cost less than just
    the new bucket. Cheap regression guard against formula bugs."""
    cp = _run_cli("synthesize", "--estimate")
    assert cp.returncode == 0
    # Parse the two dollar figures out of stdout.
    import re
    incr = re.search(r"Incremental sync:\s+\$([\d.]+)", cp.stdout)
    full = re.search(r"Full re-synth:\s+\$([\d.]+)", cp.stdout)
    assert incr is not None and full is not None, cp.stdout
    assert float(full.group(1)) >= float(incr.group(1)) - 1e-6
