"""Tests for the observability CLI bundle (G-01 · G-03 · G-13).

* ``cmd_adapters``: status helper returns right tuple, CLI shows
  ``auto``/``explicit``/``off`` + ``will_fire`` columns, legacy labels
  are gone.
* ``cmd_log``: filters by date / operation, JSON vs text output, empty
  log, missing file, invalid --since, limit clamping.
* ``cmd_sync_status``: reads ``_meta`` + ``_counters`` from the state
  file, renders per-adapter table, surfaces quarantine counts, shows
  ``--recent`` activity from log.md.
* State migration keeps ``_meta`` / ``_counters`` intact.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args, env=None):
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


# ─── G-01: _adapter_status + cmd_adapters ─────────────────────────────────


class _FakeAdapter:
    """Minimal adapter shim used by ``_adapter_status`` tests."""

    _available = True

    @classmethod
    def is_available(cls) -> bool:
        return cls._available


def _available_fake(is_avail: bool):
    klass = type(
        "Fake",
        (_FakeAdapter,),
        {"_available": is_avail},
    )
    return klass


def test_adapter_status_auto_default():
    from llmwiki.cli import _adapter_status
    configured, will_fire = _adapter_status("x", _available_fake(True), config={})
    assert configured == "auto"
    assert will_fire == "yes"


def test_adapter_status_explicit_enable():
    from llmwiki.cli import _adapter_status
    cfg = {"x": {"enabled": True}}
    configured, will_fire = _adapter_status("x", _available_fake(True), config=cfg)
    assert configured == "explicit"
    assert will_fire == "yes"


def test_adapter_status_explicit_off_blocks_fire():
    from llmwiki.cli import _adapter_status
    cfg = {"x": {"enabled": False}}
    configured, will_fire = _adapter_status("x", _available_fake(True), config=cfg)
    assert configured == "off"
    assert will_fire == "no"


def test_adapter_status_unavailable_never_fires():
    from llmwiki.cli import _adapter_status
    configured, will_fire = _adapter_status(
        "x", _available_fake(False), config={"x": {"enabled": True}}
    )
    assert will_fire == "no"


def test_adapter_status_invalid_config_entry_defaults_to_auto():
    """A malformed config row (string instead of dict) must not crash."""
    from llmwiki.cli import _adapter_status
    configured, _ = _adapter_status("x", _available_fake(True), config={"x": "yes"})
    assert configured == "auto"


def test_adapters_cli_shows_new_columns():
    cp = _run_cli("adapters")
    assert cp.returncode == 0
    # #387 U2: column names renamed to present / enabled / active.
    for header in ("name", "present", "enabled", "active", "description"):
        assert header in cp.stdout, (
            f"adapters table missing the {header!r} column header"
        )
    # Old column names should be gone — they're confusing without the legend.
    assert "configured" not in cp.stdout, "old 'configured' column header still rendered"
    assert "will_fire" not in cp.stdout, "old 'will_fire' column header still rendered"
    # Human-readable column legend at the bottom describes the new names.
    assert "auto (default)" in cp.stdout
    assert "explicit (enabled:true" in cp.stdout


def test_adapters_wide_flag_still_works():
    cp = _run_cli("adapters", "--wide")
    assert cp.returncode == 0
    assert "Pass --wide" not in cp.stdout


# ─── G-13: cmd_log ────────────────────────────────────────────────────────


SAMPLE_LOG = dedent(
    """\
    # Wiki Log

    ## [2026-04-19] synthesize | 3 sessions across 2 projects
    - Processed: 3
    - Errors: 0

    ## [2026-04-18] lint | auto-check
    - Processed: 714

    ## [2026-04-17] sync | nightly
    - Processed: 20
    """
)


@pytest.mark.skip(reason="log CLI subcommand removed")
def test_cmd_log_missing_file_returns_error(tmp_path, monkeypatch):
    pass


@pytest.mark.skip(reason="log CLI subcommand removed")
def test_cmd_log_text_format_default(tmp_path, monkeypatch, capsys):
    pass


@pytest.mark.skip(reason="log CLI subcommand removed")
def test_cmd_log_operation_filter(tmp_path, monkeypatch, capsys):
    pass


@pytest.mark.skip(reason="log CLI subcommand removed")
def test_cmd_log_since_filter(tmp_path, monkeypatch, capsys):
    pass


@pytest.mark.skip(reason="log CLI subcommand removed")
def test_cmd_log_invalid_since_returns_error(tmp_path, monkeypatch, capsys):
    pass


@pytest.mark.skip(reason="log CLI subcommand removed")
def test_cmd_log_json_format(tmp_path, monkeypatch, capsys):
    pass


@pytest.mark.skip(reason="log CLI subcommand removed")
def test_cmd_log_limit_clamps(tmp_path, monkeypatch, capsys):
    pass


@pytest.mark.skip(reason="log CLI subcommand removed")
def test_cmd_log_empty_matches_prints_helpful_message(tmp_path, monkeypatch, capsys):
    pass


@pytest.mark.skip(reason="log CLI subcommand removed")
def test_cli_log_end_to_end():
    pass


# ─── G-03: cmd_sync_status ────────────────────────────────────────────────


def test_sync_status_empty_state(tmp_path, monkeypatch, capsys):
    import llmwiki.cli as cli_mod
    import llmwiki.convert as convert_mod
    monkeypatch.setattr(convert_mod, "DEFAULT_STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path); import llmwiki.sync.status as sync_status_mod; monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)
    args = _mk_sync_status_args()
    rc = cli_mod.cmd_sync_status(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "never" in out or "pre-upgrade" in out
    assert "No per-adapter counters" in out
    assert "Quarantined sources: 0" in out


def test_sync_status_renders_counters_table(tmp_path, monkeypatch, capsys):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({
            "_meta": {"last_sync": "2026-04-20T04:00:00Z", "version": 1},
            "_counters": {
                "claude_code": {
                    "discovered": 471, "converted": 65, "unchanged": 0,
                    "live": 1, "filtered": 405, "ignored": 0, "errored": 0,
                },
                "codex_cli": {
                    "discovered": 1, "converted": 0, "unchanged": 0,
                    "live": 0, "filtered": 1, "ignored": 0, "errored": 0,
                },
            },
            "claude_code::.claude/projects/foo/a.jsonl": 1.0,
        }, indent=2),
        encoding="utf-8",
    )
    import llmwiki.cli as cli_mod
    import llmwiki.convert as convert_mod
    monkeypatch.setattr(convert_mod, "DEFAULT_STATE_FILE", state_file)
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path); import llmwiki.sync.status as sync_status_mod; monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)
    rc = cli_mod.cmd_sync_status(_mk_sync_status_args())
    assert rc == 0
    out = capsys.readouterr().out
    assert "Last sync: 2026-04-20T04:00:00Z" in out
    assert "claude_code" in out
    assert "codex_cli" in out
    # Counters columns
    for header in ("discovered", "converted", "unchanged", "live", "filtered", "errored"):
        assert header in out


def test_sync_status_surfaces_quarantine(tmp_path, monkeypatch, capsys):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({}), encoding="utf-8")
    quar_file = tmp_path / "quar.json"
    from llmwiki import quarantine as q
    q.add_entry("claude_code", "/tmp/bad.jsonl", "boom", path=quar_file)

    import llmwiki.cli as cli_mod
    import llmwiki.convert as convert_mod
    monkeypatch.setattr(convert_mod, "DEFAULT_STATE_FILE", state_file)
    monkeypatch.setattr(q, "DEFAULT_QUARANTINE_FILE", quar_file)
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path); import llmwiki.sync.status as sync_status_mod; monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)

    rc = cli_mod.cmd_sync_status(_mk_sync_status_args())
    assert rc == 0
    out = capsys.readouterr().out
    assert "Quarantined sources: 1" in out
    assert "claude_code:1" in out


def test_sync_status_with_recent_logs_events(tmp_path, monkeypatch, capsys):
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "log.md").write_text(SAMPLE_LOG, encoding="utf-8")
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({}), encoding="utf-8")
    import llmwiki.cli as cli_mod
    import llmwiki.convert as convert_mod
    monkeypatch.setattr(convert_mod, "DEFAULT_STATE_FILE", state_file)
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path); import llmwiki.sync.status as sync_status_mod; monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)
    rc = cli_mod.cmd_sync_status(_mk_sync_status_args(recent=2))
    assert rc == 0
    out = capsys.readouterr().out
    assert "Recent activity" in out
    # SAMPLE_LOG only has one sync/synthesize pair (synthesize on 4-19, sync on 4-17)
    assert "2026-04-19" in out
    assert "2026-04-17" in out


def test_sync_status_corrupt_state_file_is_tolerated(tmp_path, monkeypatch, capsys):
    state_file = tmp_path / "state.json"
    state_file.write_text("{ not json", encoding="utf-8")
    import llmwiki.cli as cli_mod
    import llmwiki.convert as convert_mod
    monkeypatch.setattr(convert_mod, "DEFAULT_STATE_FILE", state_file)
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path); import llmwiki.sync.status as sync_status_mod; monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)
    rc = cli_mod.cmd_sync_status(_mk_sync_status_args())
    assert rc == 0


def test_cli_sync_status_flag_short_circuits(monkeypatch):
    """`llmwiki sync --status` must not try to run a real sync."""
    cp = _run_cli("sync", "--status")
    # Either reports observability (rc=0) or complains about env, but
    # should never crash with a traceback.
    assert "Traceback" not in cp.stderr
    assert cp.returncode in (0, 1)


# ─── state migration preserves _meta / _counters ──────────────────────────


def test_migrate_preserves_underscore_prefixed_keys(tmp_path):
    from llmwiki.convert import _migrate_legacy_state
    legacy = {
        "_meta": {"last_sync": "2026-04-20T00:00:00Z"},
        "_counters": {"claude_code": {"discovered": 10}},
        "claude_code::.claude/projects/x/a.jsonl": 1.0,
    }
    migrated, count = _migrate_legacy_state(legacy, ["claude_code"])
    assert "_meta" in migrated
    assert migrated["_meta"]["last_sync"] == "2026-04-20T00:00:00Z"
    assert "_counters" in migrated
    assert migrated["_counters"]["claude_code"]["discovered"] == 10
    assert count == 0  # no legacy absolute paths in this fixture


def test_migrate_preserves_meta_through_legacy_path_rewrite(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    legacy_abs = str(tmp_path / ".claude" / "projects" / "x" / "old.jsonl")
    legacy = {
        "_meta": {"last_sync": "2026-04-20T00:00:00Z"},
        legacy_abs: 1.0,
    }
    from llmwiki.convert import _migrate_legacy_state
    migrated, count = _migrate_legacy_state(legacy, ["claude_code"])
    assert count == 1
    assert "_meta" in migrated
    assert any(k.startswith("claude_code::") for k in migrated if not k.startswith("_"))


# ─── test helpers ─────────────────────────────────────────────────────────


def _mk_log_args(*, limit=10, operation=None, since=None, format="text"):
    class _A:
        pass
    a = _A()
    a.limit = limit
    a.operation = operation
    a.since = since
    a.format = format
    return a


def _mk_sync_status_args(*, recent=0):
    class _A:
        pass
    a = _A()
    a.recent = recent
    return a
