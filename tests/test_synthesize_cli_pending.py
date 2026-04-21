"""Tests for the ``llmwiki synthesize --list-pending`` + ``--complete``
CLI subcommands (#316 follow-up).

Covers:

* ``--list-pending`` with no prompts → 0 exit + "No pending prompts."
* ``--list-pending`` with prompts → table with uuid + slug + project
* ``--complete`` without ``--page`` → 1 exit + helpful message
* ``--complete`` with body from ``--body`` file → rewrites the page
* ``--complete`` with body from stdin → rewrites the page
* ``--complete`` with missing target page → 1 exit
* ``--complete`` with no sentinel on the target page → 1 exit
* ``--complete`` with uuid mismatch → 1 exit
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args: str, cwd: Path, input_text: str = "") -> subprocess.CompletedProcess:
    """Run the `llmwiki` CLI in a subprocess so argparse + stdin behave
    like a real user invocation.  Always uses the current Python and
    injects REPO_ROOT into PYTHONPATH so ``python -m llmwiki`` resolves
    even when ``cwd`` is a scratch dir."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(REPO_ROOT) + (os.pathsep + existing if existing else "")
    )
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        input=input_text,
        env=env,
    )


# ─── shared fixture: isolate from the real .llmwiki-pending-prompts/ ─


@pytest.fixture
def scratch_repo(tmp_path, monkeypatch):
    """A sandbox that mirrors the layout enough for `llmwiki synthesize`
    to work on its pending-prompts subfolder.  We monkeypatch REPO_ROOT
    inside the subprocess by setting the CWD to ``tmp_path`` and
    copying/linking the installed llmwiki package into ``sys.path``.

    Simpler: since ``llmwiki.REPO_ROOT`` is resolved from ``llmwiki/__init__.py``'s
    location (it is NOT driven by CWD), we can't point it at ``tmp_path`` via
    subprocess alone.  Instead, write the pending-prompts dir at the real
    REPO_ROOT and clean up afterwards.  This means we use the real module and
    actually exercise the CLI, but we MUST clean up in a ``finally`` block.
    """
    pending = REPO_ROOT / ".llmwiki-pending-prompts"
    created_files: list[Path] = []
    yield pending, created_files
    # Cleanup — remove only the files this test created.
    for p in created_files:
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    # If we created the directory and it's now empty, remove it.
    if pending.exists() and not any(pending.iterdir()):
        try:
            pending.rmdir()
        except OSError:
            pass


# ─── --list-pending ───────────────────────────────────────────────────


def test_list_pending_no_prompts(scratch_repo, monkeypatch):
    pending, _ = scratch_repo
    # Make sure there's nothing pending for this test.
    if pending.exists():
        for p in pending.glob("*.md"):
            # Don't touch existing real prompts; skip if any present.
            pytest.skip("real pending prompts present — skipping to avoid disturbing them")
    result = _run_cli("synthesize", "--list-pending", cwd=REPO_ROOT)
    assert result.returncode == 0
    assert "No pending prompts" in result.stdout


def test_list_pending_with_prompts(scratch_repo):
    pending, created = scratch_repo
    pending.mkdir(parents=True, exist_ok=True)
    uid = "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"
    prompt = pending / f"{uid}.md"
    prompt.write_text(
        "<!-- pending-slug: test-slug -->\n"
        "<!-- pending-project: test-project -->\n"
        "<!-- pending-date: 2026-04-21 -->\n\n"
        "Prompt body goes here.",
        encoding="utf-8",
    )
    created.append(prompt)

    result = _run_cli("synthesize", "--list-pending", cwd=REPO_ROOT)
    assert result.returncode == 0
    assert uid in result.stdout
    assert "test-slug" in result.stdout
    assert "test-project" in result.stdout
    assert "2026-04-21" in result.stdout
    assert "pending prompt" in result.stdout  # "N pending prompt(s)."


# ─── --complete argument validation ──────────────────────────────────


def test_complete_without_page_exits_1(tmp_path):
    result = _run_cli("synthesize", "--complete", "deadbeef", cwd=tmp_path)
    assert result.returncode == 1
    assert "--page" in result.stderr


def test_complete_without_body_or_stdin_exits_1(tmp_path):
    page = tmp_path / "p.md"
    page.write_text("stub", encoding="utf-8")
    result = _run_cli(
        "synthesize", "--complete", "deadbeef", "--page", str(page),
        cwd=tmp_path,
    )
    # stdin is empty string → body empty → error
    assert result.returncode == 1
    assert "body" in result.stderr.lower()


def test_complete_missing_page_file(tmp_path):
    result = _run_cli(
        "synthesize", "--complete", "deadbeef",
        "--page", str(tmp_path / "nope.md"),
        cwd=tmp_path,
        input_text="some body",
    )
    assert result.returncode == 1
    # FileNotFoundError from agent_delegate.complete_pending
    assert "not found" in result.stderr.lower()


def test_complete_page_without_sentinel(tmp_path):
    page = tmp_path / "clean.md"
    page.write_text(
        "---\ntitle: x\n---\n\n## Summary\n\nNo sentinel here.\n",
        encoding="utf-8",
    )
    result = _run_cli(
        "synthesize", "--complete", "00000000-0000-0000-0000-000000000000",
        "--page", str(page),
        cwd=tmp_path,
        input_text="## Summary\n\nBody.\n",
    )
    assert result.returncode == 1
    assert "sentinel" in result.stderr.lower()


def test_complete_uuid_mismatch(tmp_path):
    actual_uid = "11111111-1111-1111-1111-111111111111"
    page = tmp_path / "placeholder.md"
    page.write_text(
        "---\ntitle: x\n---\n\n"
        f"<!-- llmwiki-pending: {actual_uid} -->\n\n"
        "## Summary\n\nPending.\n",
        encoding="utf-8",
    )
    result = _run_cli(
        "synthesize", "--complete", "22222222-2222-2222-2222-222222222222",
        "--page", str(page),
        cwd=tmp_path,
        input_text="## Summary\n\nBody.\n",
    )
    assert result.returncode == 1
    assert "uuid" in result.stderr.lower()


# ─── --complete happy paths ──────────────────────────────────────────


def test_complete_with_body_file(tmp_path):
    uid = "33333333-3333-3333-3333-333333333333"
    page = tmp_path / "placeholder.md"
    page.write_text(
        "---\ntitle: x\ntags: [claude-code]\n---\n\n"
        f"<!-- llmwiki-pending: {uid} -->\n\n"
        "## Summary\n\nPending.\n",
        encoding="utf-8",
    )
    body_file = tmp_path / "body.md"
    body_file.write_text("## Summary\n\nAgent synthesis body.\n", encoding="utf-8")

    result = _run_cli(
        "synthesize", "--complete", uid,
        "--page", str(page),
        "--body", str(body_file),
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    final = page.read_text(encoding="utf-8")
    assert "tags: [claude-code]" in final  # frontmatter preserved
    assert "Agent synthesis body." in final  # body in place
    assert "llmwiki-pending" not in final  # sentinel gone


def test_complete_with_stdin(tmp_path):
    uid = "44444444-4444-4444-4444-444444444444"
    page = tmp_path / "placeholder.md"
    page.write_text(
        "---\ntitle: x\n---\n\n"
        f"<!-- llmwiki-pending: {uid} -->\n\n"
        "## Summary\n\nPending.\n",
        encoding="utf-8",
    )

    result = _run_cli(
        "synthesize", "--complete", uid,
        "--page", str(page),
        cwd=tmp_path,
        input_text="## Summary\n\nStdin-supplied body.\n",
    )
    assert result.returncode == 0, result.stderr
    final = page.read_text(encoding="utf-8")
    assert "Stdin-supplied body." in final
    assert "llmwiki-pending" not in final
