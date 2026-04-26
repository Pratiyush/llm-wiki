"""Tests for #426 — `_meta` / `_counters` persistence under `--force`.

The bug: `convert_all`'s state-write block was guarded by
``if not dry_run and not force``. With ``--force``, every per-key
``state[key] = mtime`` update made during the loop *and* the
observability snapshot (`_meta.last_sync`, `_counters`) were discarded.
That means:

1. ``llmwiki sync --status`` after a ``sync --force`` shows the
   *previous* run's `last_sync`, silently losing the audit trail.
2. The next plain `sync` re-processes every file because no state
   was recorded for the just-completed forced run.

The fix lifts the ``not force`` half of the guard. ``--force`` is
about *ignoring prior state on read* (re-process even unchanged
files), not about skipping the new state record on write.

These tests exercise `convert_all` end-to-end through a faked-out
adapter so we don't need a real Claude Code corpus on disk. Each
case checks both the on-disk JSON and the in-memory state structure.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki import convert as convert_mod
from llmwiki.convert import convert_all, load_state, save_state


# ─── Fixtures ────────────────────────────────────────────────────────────


def _seed_jsonl(repo: Path, project: str, name: str, body: str = "") -> Path:
    """Drop a minimal Claude-Code-style .jsonl file under the fake home."""
    src = repo / ".claude" / "projects" / project
    src.mkdir(parents=True, exist_ok=True)
    path = src / f"{name}.jsonl"
    record = {
        "type": "summary",
        "summary": body or "Test session",
        "uuid": f"{name}-uuid",
        "timestamp": "2026-04-26T01:00:00.000Z",
    }
    user_record = {
        "type": "user",
        "uuid": f"{name}-user",
        "timestamp": "2026-04-26T01:00:30.000Z",
        "message": {"role": "user", "content": body or "hello"},
        "cwd": f"/Users/test/{project}",
    }
    asst_record = {
        "type": "assistant",
        "uuid": f"{name}-asst",
        "timestamp": "2026-04-26T01:00:31.000Z",
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-4-5",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    }
    path.write_text(
        "\n".join(json.dumps(r) for r in (record, user_record, asst_record)) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Stand up a tmp HOME with one Claude Code session, plus point
    convert.DEFAULT_OUT_DIR / DEFAULT_STATE_FILE under tmp_path.

    `Path.home()` patching alone is insufficient because
    `ClaudeCodeAdapter.session_store_path` is computed at class-define
    time (import-time), so the cached path still points at the real
    home. We override the class attribute directly so discovery walks
    our tmp tree on every CI runner.
    """
    from llmwiki.adapters.claude_code import ClaudeCodeAdapter

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(
        ClaudeCodeAdapter,
        "session_store_path",
        tmp_path / ".claude" / "projects",
    )
    out_dir = tmp_path / "raw" / "sessions"
    state_file = tmp_path / ".llmwiki-sync-state.json"
    config_file = tmp_path / "sessions_config.json"
    ignore_file = tmp_path / ".llmwiki-ignore"
    config_file.write_text("{}", encoding="utf-8")
    _seed_jsonl(tmp_path, "demo-proj", "session-one")
    return {
        "root": tmp_path,
        "out_dir": out_dir,
        "state_file": state_file,
        "config_file": config_file,
        "ignore_file": ignore_file,
    }


def _run(fake_repo, **kw):
    """Invoke convert_all with the fake-repo paths bound."""
    return convert_all(
        adapters=["claude_code"],
        out_dir=fake_repo["out_dir"],
        state_file=fake_repo["state_file"],
        config_file=fake_repo["config_file"],
        ignore_file=fake_repo["ignore_file"],
        include_current=True,
        **kw,
    )


# ─── Default behaviour (regression guard) ────────────────────────────────


def test_default_sync_writes_meta_and_counters(fake_repo):
    rc = _run(fake_repo)
    assert rc == 0
    state = json.loads(fake_repo["state_file"].read_text())
    assert "_meta" in state, "default sync must persist _meta"
    assert "last_sync" in state["_meta"]
    assert "_counters" in state, "default sync must persist _counters"
    assert "claude_code" in state["_counters"]


def test_default_sync_persists_per_key_state(fake_repo):
    """The mtime keys for each processed file land on disk."""
    _run(fake_repo)
    state = json.loads(fake_repo["state_file"].read_text())
    file_keys = [k for k in state if not k.startswith("_")]
    assert file_keys, f"expected portable adapter::path keys, got {list(state)}"
    assert any(k.startswith("claude_code::") for k in file_keys)


# ─── #426: --force still writes _meta / _counters ─────────────────────────


def test_force_sync_writes_meta(fake_repo):
    """Regression for #426. Before the fix, this assertion failed —
    --force discarded every state-file write."""
    _run(fake_repo)  # seed first run
    pre_meta = json.loads(fake_repo["state_file"].read_text())["_meta"]["last_sync"]

    # Touch the source so the second run has work to do.
    src = fake_repo["root"] / ".claude" / "projects" / "demo-proj" / "session-one.jsonl"
    src.write_text(src.read_text() + "\n", encoding="utf-8")

    rc = _run(fake_repo, force=True)
    assert rc == 0
    state = json.loads(fake_repo["state_file"].read_text())
    assert "_meta" in state, (
        "--force discarded _meta — #426 regression"
    )
    # Either same timestamp (sub-second resolution) or strictly newer; both prove
    # the write happened. The original bug left _meta == pre_meta exactly because
    # the forced run never wrote at all.
    post_meta = state["_meta"]["last_sync"]
    assert post_meta >= pre_meta


def test_force_sync_writes_counters(fake_repo):
    _run(fake_repo)  # seed
    rc = _run(fake_repo, force=True)
    assert rc == 0
    state = json.loads(fake_repo["state_file"].read_text())
    assert "_counters" in state
    assert "claude_code" in state["_counters"]
    # Force re-processes the file, so converted should be >= 1.
    assert state["_counters"]["claude_code"].get("converted", 0) >= 1


def test_force_sync_persists_per_key_state(fake_repo):
    """Force still records the per-key mtime so the next plain sync
    can correctly identify the file as unchanged."""
    rc = _run(fake_repo, force=True)
    assert rc == 0
    state = json.loads(fake_repo["state_file"].read_text())
    file_keys = [k for k in state if not k.startswith("_")]
    assert file_keys, "force sync must persist per-key state"


def test_force_then_plain_sync_identifies_unchanged(fake_repo):
    """End-to-end consequence of the fix: after a forced re-sync,
    a plain follow-up sync should treat the same file as unchanged."""
    rc1 = _run(fake_repo, force=True)
    assert rc1 == 0
    counters_after_force = json.loads(
        fake_repo["state_file"].read_text()
    )["_counters"]["claude_code"]
    assert counters_after_force.get("converted", 0) >= 1

    # Second plain run — file mtime is the same, state is recorded, so
    # the adapter should mark this as 'unchanged' not 'converted'.
    rc2 = _run(fake_repo)
    assert rc2 == 0
    state = json.loads(fake_repo["state_file"].read_text())
    counters = state["_counters"]["claude_code"]
    assert counters.get("unchanged", 0) >= 1, (
        f"plain sync after --force re-processed instead of skipping: {counters}"
    )


# ─── --dry-run wins over --force ─────────────────────────────────────────


def test_dry_run_does_not_write_meta(fake_repo):
    """Dry-run is observation-only — must NOT touch the state file."""
    rc = _run(fake_repo, dry_run=True)
    assert rc == 0
    assert not fake_repo["state_file"].exists(), (
        "dry-run wrote to state file"
    )


def test_force_and_dry_run_combined_does_not_write(fake_repo):
    """When both flags are set, dry-run wins. State file untouched."""
    rc = _run(fake_repo, force=True, dry_run=True)
    assert rc == 0
    assert not fake_repo["state_file"].exists(), (
        "--force --dry-run wrote to state file — dry-run must win"
    )


# ─── Corrupt state file is gracefully re-created with new _meta ──────────


def test_force_recreates_meta_on_corrupt_state(fake_repo):
    """If the state file exists but is corrupt JSON, --force should
    still produce a clean new state with _meta + _counters populated."""
    fake_repo["state_file"].write_text("{not valid json", encoding="utf-8")
    rc = _run(fake_repo, force=True)
    assert rc == 0
    state = json.loads(fake_repo["state_file"].read_text())
    assert "_meta" in state and "last_sync" in state["_meta"]
    assert "_counters" in state


# ─── First-ever sync populates _meta + _counters ─────────────────────────


def test_first_sync_populates_meta(fake_repo):
    """No prior state file at all. The very first sync should land
    a fully-populated state file."""
    assert not fake_repo["state_file"].exists()
    rc = _run(fake_repo)
    assert rc == 0
    state = json.loads(fake_repo["state_file"].read_text())
    assert state["_meta"]["version"] == 1
    assert state["_counters"]["claude_code"]["converted"] >= 1


# ─── Counters aggregate the adapter buckets seen this run ────────────────


def test_counters_include_all_status_buckets(fake_repo):
    """_counters['claude_code'] must contain the full set of buckets
    even when most are zero — downstream `sync --status` rendering
    relies on every key being present."""
    _run(fake_repo, force=True)
    state = json.loads(fake_repo["state_file"].read_text())
    bucket = state["_counters"]["claude_code"]
    for key in ("discovered", "converted", "unchanged", "live",
                "filtered", "ignored", "errored"):
        assert key in bucket, f"missing bucket {key} in counters"


# ─── Force sync preserves prior _meta until overwrite ────────────────────


def test_force_overwrites_prior_meta(fake_repo):
    """The new run's _meta replaces the prior one — _meta is a
    snapshot, not an append-only log."""
    fake_repo["state_file"].write_text(
        json.dumps({
            "_meta": {"last_sync": "2020-01-01T00:00:00Z", "version": 1},
            "_counters": {"claude_code": {"discovered": 0}},
        }),
        encoding="utf-8",
    )
    rc = _run(fake_repo, force=True)
    assert rc == 0
    state = json.loads(fake_repo["state_file"].read_text())
    assert state["_meta"]["last_sync"] != "2020-01-01T00:00:00Z"
