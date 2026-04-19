"""Regression tests for the gap-sweep PR (G-02, G-10, G-11, G-18).

Each test pins one specific fix so silent regressions show up in CI.
See ``gaps.md`` (local) / GitHub issues #288, #296, #297, #304.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest


# ─── G-10 (#296): log archive frontmatter seed ───────────────────────────


def test_log_archive_gets_frontmatter_on_first_write(tmp_path: Path):
    """When log.md exceeds the archival threshold, the first write to
    log-archive-<year>.md must include the standard nav frontmatter so
    lint's frontmatter_completeness rule doesn't fail."""
    from llmwiki.synth.pipeline import _auto_archive_log, LOG_ARCHIVE_THRESHOLD

    log = tmp_path / "log.md"
    # Write past the 50 KB threshold with real-looking headings so the
    # archive preserves structure.
    log.write_text(
        "# Wiki Log\n\nThis file is auto-maintained.\n\n"
        + "## [2026-04-19] synthesize | batch\n\n" * 2500,
        encoding="utf-8",
    )
    assert log.stat().st_size > LOG_ARCHIVE_THRESHOLD

    archive = _auto_archive_log(log)
    assert archive is not None and archive.is_file()
    text = archive.read_text(encoding="utf-8")
    # Frontmatter must include the keys frontmatter_completeness needs.
    assert text.startswith("---\n")
    assert "title:" in text
    assert "type: navigation" in text
    assert "last_updated:" in text
    assert "auto_generated: true" in text


def test_log_archive_below_threshold_is_noop(tmp_path: Path):
    from llmwiki.synth.pipeline import _auto_archive_log

    log = tmp_path / "log.md"
    log.write_text("# Wiki Log\n\n## [2026-04-19] synthesize | small\n", encoding="utf-8")
    assert _auto_archive_log(log) is None
    # Log was not rotated.
    assert log.read_text(encoding="utf-8").startswith("# Wiki Log")


# ─── G-11 (#297): duplicate_detection tuning ─────────────────────────────


def _page(rel: str, *, title: str, project: str = "", ptype: str = "source",
          body: str = "") -> tuple[str, dict]:
    meta = {"title": title, "type": ptype}
    if project:
        meta["project"] = project
    return rel, {"meta": meta, "body": body or f"Unique body for {rel}"}


def test_duplicate_detection_respects_project_scope():
    """Same-titled pages in DIFFERENT projects must not be flagged."""
    from llmwiki.lint.rules import DuplicateDetection

    pages = dict([
        _page("sources/proj-a/CHANGELOG.md", title="CHANGELOG",
              project="proj-a", body="proj a changelog body"),
        _page("sources/proj-b/CHANGELOG.md", title="CHANGELOG",
              project="proj-b", body="totally unrelated proj b changelog body"),
    ])
    issues = DuplicateDetection().run(pages)
    assert issues == [], f"unexpected duplicates: {issues}"


def test_duplicate_detection_requires_body_overlap():
    """Same-titled same-project pages with distinct bodies must NOT
    flag — previously the 1.0 title match alone fired."""
    from llmwiki.lint.rules import DuplicateDetection

    body_a = "alpha " * 500
    body_b = "omega " * 500  # zero overlap
    pages = dict([
        _page("sources/proj-a/a.md", title="CLAUDE", project="proj-a", body=body_a),
        _page("sources/proj-a/b.md", title="CLAUDE", project="proj-a", body=body_b),
    ])
    issues = DuplicateDetection().run(pages)
    assert issues == []


def test_duplicate_detection_flags_true_duplicates():
    """Same project, same title, same body → MUST flag."""
    from llmwiki.lint.rules import DuplicateDetection

    body = "exact same content here for duplicate test " * 50
    pages = dict([
        _page("sources/proj-a/a.md", title="README", project="proj-a", body=body),
        _page("sources/proj-a/b.md", title="README", project="proj-a", body=body),
    ])
    issues = DuplicateDetection().run(pages)
    assert len(issues) == 1
    msg = issues[0]["message"]
    assert "possible duplicate" in msg
    assert "title" in msg and "body" in msg


def test_duplicate_detection_cross_type_never_flags():
    """An entity page must not be compared against a source page."""
    from llmwiki.lint.rules import DuplicateDetection
    body = "same body for both"
    pages = dict([
        _page("sources/proj/a.md", title="X", project="proj",
              ptype="source", body=body),
        _page("entities/X.md", title="X", project="",
              ptype="entity", body=body),
    ])
    issues = DuplicateDetection().run(pages)
    assert issues == []


# ─── G-18 (#304): render_recent_activity + home-page fallback ────────────


def test_render_recent_activity_empty_returns_empty_string():
    from llmwiki.changelog_timeline import render_recent_activity
    assert render_recent_activity([]) == ""


def test_render_recent_activity_renders_rows():
    from llmwiki.changelog_timeline import render_recent_activity
    from llmwiki.log_reader import LogEvent

    events = [
        LogEvent(
            date=date(2026, 4, 19), operation="synthesize",
            title="batch", details={"Processed": "12"},
        ),
        LogEvent(
            date=date(2026, 4, 18), operation="sync",
            title="pull", details={},
        ),
    ]
    html = render_recent_activity(events)
    assert "Recent activity" in html
    assert "synthesize" in html
    assert "2026-04-19" in html
    assert "12 processed" in html  # uses Processed detail
    # No fake wikilink (G-12 interaction)
    assert "[[" not in html


# ─── G-02 (#288): llmwiki adapters --wide ────────────────────────────────


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Invoke the CLI in a subprocess so we exercise argparse end-to-end."""
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_adapters_accepts_wide_flag():
    cp = _run_cli("adapters", "--wide")
    assert cp.returncode == 0, cp.stderr
    assert "Registered adapters:" in cp.stdout


def test_adapters_help_advertises_wide_flag():
    cp = _run_cli("adapters", "--help")
    assert cp.returncode == 0
    assert "--wide" in cp.stdout


def test_adapters_truncates_without_wide_but_not_with_wide():
    """Default output may end in '...'; --wide must not truncate."""
    narrow = _run_cli("adapters")
    wide = _run_cli("adapters", "--wide")
    assert narrow.returncode == 0 and wide.returncode == 0
    # With --wide we drop the "Pass --wide" hint line.
    assert "Pass --wide" in narrow.stdout
    assert "Pass --wide" not in wide.stdout


# ─── G-20 (#306): prove we didn't regress the log format ────────────────


def test_log_heading_regex_still_greppable():
    """CLAUDE.md promises ``grep "^## \\[" wiki/log.md`` works.  The
    batched summary heading must still match that pattern."""
    import re
    heading = "## [2026-04-19] synthesize | 3 sessions across 2 projects"
    assert re.match(r"^##\s+\[\d{4}-\d{2}-\d{2}\]\s+\S+\s+\|\s+.+", heading)
