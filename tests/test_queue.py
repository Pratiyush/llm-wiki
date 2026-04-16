"""Tests for the pending ingest queue (v1.0, #148)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.queue import enqueue, dequeue, peek, clear, queue_size


# ─── Basic operations ──────────────────────────────────────────────────


def test_enqueue_creates_file(tmp_path: Path):
    qf = tmp_path / "queue.json"
    count = enqueue(["raw/sessions/a.md"], queue_file=qf)
    assert count == 1
    assert qf.exists()


def test_peek_returns_items(tmp_path: Path):
    qf = tmp_path / "queue.json"
    enqueue(["raw/a.md", "raw/b.md"], queue_file=qf)
    items = peek(queue_file=qf)
    assert set(items) == {"raw/a.md", "raw/b.md"}


def test_dequeue_returns_and_clears(tmp_path: Path):
    qf = tmp_path / "queue.json"
    enqueue(["raw/a.md", "raw/b.md"], queue_file=qf)
    items = dequeue(queue_file=qf)
    assert len(items) == 2
    assert queue_size(queue_file=qf) == 0


def test_clear_empties_queue(tmp_path: Path):
    qf = tmp_path / "queue.json"
    enqueue(["raw/a.md"], queue_file=qf)
    clear(queue_file=qf)
    assert queue_size(queue_file=qf) == 0


def test_queue_size(tmp_path: Path):
    qf = tmp_path / "queue.json"
    assert queue_size(queue_file=qf) == 0
    enqueue(["raw/a.md", "raw/b.md", "raw/c.md"], queue_file=qf)
    assert queue_size(queue_file=qf) == 3


# ─── Deduplication ─────────────────────────────────────────────────────


def test_enqueue_deduplicates(tmp_path: Path):
    qf = tmp_path / "queue.json"
    enqueue(["raw/a.md", "raw/a.md", "raw/a.md"], queue_file=qf)
    assert queue_size(queue_file=qf) == 1


def test_enqueue_deduplicates_across_calls(tmp_path: Path):
    qf = tmp_path / "queue.json"
    enqueue(["raw/a.md", "raw/b.md"], queue_file=qf)
    enqueue(["raw/b.md", "raw/c.md"], queue_file=qf)
    assert queue_size(queue_file=qf) == 3


# ─── Edge cases ────────────────────────────────────────────────────────


def test_peek_empty_queue(tmp_path: Path):
    qf = tmp_path / "queue.json"
    assert peek(queue_file=qf) == []


def test_dequeue_empty_queue(tmp_path: Path):
    qf = tmp_path / "queue.json"
    assert dequeue(queue_file=qf) == []


def test_enqueue_empty_list(tmp_path: Path):
    qf = tmp_path / "queue.json"
    count = enqueue([], queue_file=qf)
    assert count == 0


def test_corrupt_queue_file(tmp_path: Path):
    qf = tmp_path / "queue.json"
    qf.write_text("NOT JSON", encoding="utf-8")
    assert peek(queue_file=qf) == []  # graceful recovery


def test_queue_with_non_string_items(tmp_path: Path):
    """Non-string items in the JSON array are skipped."""
    qf = tmp_path / "queue.json"
    qf.write_text('[123, null, "raw/a.md", true]', encoding="utf-8")
    items = peek(queue_file=qf)
    assert items == ["raw/a.md"]


def test_sorted_output(tmp_path: Path):
    qf = tmp_path / "queue.json"
    enqueue(["raw/c.md", "raw/a.md", "raw/b.md"], queue_file=qf)
    items = peek(queue_file=qf)
    assert items == sorted(items)


def test_clear_nonexistent_file(tmp_path: Path):
    qf = tmp_path / "queue.json"
    clear(queue_file=qf)  # should not raise
