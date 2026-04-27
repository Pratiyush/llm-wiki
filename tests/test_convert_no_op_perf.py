"""Regression tests for #arch-h9 / #612 — no-op sync skips derive_project_slug.

Pre-fix, ``convert_all`` called ``adapter.derive_project_slug(path)``
BEFORE the mtime check, which on Codex CLI opens every .jsonl to read
the session_meta cwd field. On a 5k-session corpus that's 5k needless
file opens per no-op sync. The fix reordered the per-session loop so
mtime is checked first; slug derivation only runs when the file
actually needs conversion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llmwiki.adapters import REGISTRY
from llmwiki.adapters.base import BaseAdapter
from llmwiki.convert import convert_all


class _CountingAdapter(BaseAdapter):
    """Test adapter that counts how often derive_project_slug is called."""

    name = "counting_adapter"
    is_ai_session = True

    derive_count = 0
    fixture_dir: Path

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)

    @classmethod
    def is_available(cls) -> bool:
        return True

    @property
    def session_store_path(self) -> list[Path]:
        return [self.__class__.fixture_dir]

    def discover_sessions(self) -> list[Path]:
        return sorted(self.__class__.fixture_dir.rglob("*.jsonl"))

    def derive_project_slug(self, path: Path) -> str:
        # Track every call so the test can assert no-op syncs don't trigger this.
        type(self).derive_count += 1
        # Pretend this is expensive (mirroring CodexCliAdapter's open()).
        with open(path, encoding="utf-8") as f:
            f.read(1)
        return path.parent.name


def _write_jsonl(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_session(path: Path, slug: str) -> None:
    """Write a tiny but valid Claude-Code-shaped jsonl that survives parse_jsonl."""
    rec = {
        "type": "user",
        "uuid": "u-1",
        "timestamp": "2026-04-27T00:00:00Z",
        "message": {"content": [{"type": "text", "text": f"hello {slug}"}]},
    }
    _write_jsonl(path, json.dumps(rec) + "\n")


@pytest.fixture
def counting_adapter_registered(tmp_path, monkeypatch):
    """Register _CountingAdapter into REGISTRY for the duration of the test."""
    fixture_dir = tmp_path / "sessions" / "demo-project"
    fixture_dir.parent.mkdir(parents=True, exist_ok=True)
    fixture_dir.mkdir()
    _CountingAdapter.fixture_dir = fixture_dir
    _CountingAdapter.derive_count = 0

    # Insert into REGISTRY without affecting other tests.
    REGISTRY[_CountingAdapter.name] = _CountingAdapter
    yield fixture_dir
    REGISTRY.pop(_CountingAdapter.name, None)


def test_no_op_sync_does_not_call_derive_project_slug(
    counting_adapter_registered, tmp_path
):
    """#612: a no-op sync (state matches mtime) skips derive_project_slug.

    Steps:
      1. Create 3 sessions
      2. Run convert_all once → counts go up (3 conversions)
      3. Reset derive_count
      4. Run convert_all again with the SAME state file → all 3 should
         skip via the mtime check, derive_project_slug must NOT run.
    """
    fixture_dir = counting_adapter_registered
    out_dir = tmp_path / "raw" / "sessions"
    state_file = tmp_path / ".llmwiki-state.json"
    config_file = tmp_path / "sessions_config.json"
    ignore_file = tmp_path / ".llmwikiignore"

    _make_session(fixture_dir / "a.jsonl", "a")
    _make_session(fixture_dir / "b.jsonl", "b")
    _make_session(fixture_dir / "c.jsonl", "c")

    # First run — converts all 3.
    rc = convert_all(
        adapters=[_CountingAdapter.name],
        out_dir=out_dir,
        state_file=state_file,
        config_file=config_file,
        ignore_file=ignore_file,
        include_current=True,  # don't filter "live" recent sessions
    )
    assert rc == 0
    first_run_calls = _CountingAdapter.derive_count
    # During the first run derive_project_slug runs once per session
    # (only when mtime changed — which it has, all 3 are new).
    assert first_run_calls >= 3

    # Reset the counter and run again. State + mtimes unchanged.
    _CountingAdapter.derive_count = 0
    rc = convert_all(
        adapters=[_CountingAdapter.name],
        out_dir=out_dir,
        state_file=state_file,
        config_file=config_file,
        ignore_file=ignore_file,
        include_current=True,
    )
    assert rc == 0

    # The whole point of the fix: no-op sync MUST NOT call
    # derive_project_slug. On a 5k-session corpus this is the
    # difference between 5k file opens and 0.
    assert _CountingAdapter.derive_count == 0, (
        f"no-op sync called derive_project_slug "
        f"{_CountingAdapter.derive_count} times — should have skipped "
        f"via the mtime check (#612 / #arch-h9)"
    )
