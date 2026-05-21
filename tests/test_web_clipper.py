"""Tests for the Web Clipper intake path (v1.0, #149)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki.web_clipper import load_web_clipper_config, scan_for_clips
from llmwiki.queue import peek


# ─── Config loading ───────────────────────────────────────────────────


def test_config_defaults():
    cfg = load_web_clipper_config({})
    assert cfg["enabled"] is False
    assert cfg["extensions"] == [".md"]
    assert cfg["auto_queue"] is True


def test_config_custom():
    cfg = load_web_clipper_config({
        "web_clipper": {
            "enabled": True,
            "watch_dir": "/tmp/clips",
            "extensions": [".md", ".txt"],
            "auto_queue": False,
        }
    })
    assert cfg["enabled"] is True
    assert str(cfg["watch_dir"]).replace("\\", "/") == "/tmp/clips"
    assert cfg["extensions"] == [".md", ".txt"]
    assert cfg["auto_queue"] is False


# ─── Scanning ─────────────────────────────────────────────────────────


def test_scan_disabled(tmp_path: Path):
    """Disabled clipper returns empty."""
    result = scan_for_clips(
        config={"web_clipper": {"enabled": False}},
        queue_file=tmp_path / "q.json",
    )
    assert result == []


def test_scan_missing_dir(tmp_path: Path):
    """Non-existent watch dir returns empty."""
    result = scan_for_clips(
        config={
            "web_clipper": {
                "enabled": True,
                "watch_dir": str(tmp_path / "nonexistent"),
            }
        },
        queue_file=tmp_path / "q.json",
    )
    assert result == []


def test_scan_finds_md_files(tmp_path: Path):
    """Finds .md files in the watch directory."""
    watch = tmp_path / "clips"
    watch.mkdir()
    (watch / "article1.md").write_text("# Article 1\n", encoding="utf-8")
    (watch / "article2.md").write_text("# Article 2\n", encoding="utf-8")
    (watch / "notes.txt").write_text("text file\n", encoding="utf-8")  # not .md

    # Patch REPO_ROOT so relative paths work
    with patch("llmwiki.web_clipper.REPO_ROOT", tmp_path):
        result = scan_for_clips(
            config={
                "web_clipper": {
                    "enabled": True,
                    "watch_dir": str(watch),
                }
            },
            queue_file=tmp_path / "q.json",
        )
    assert len(result) == 2
    assert any("article1.md" in r for r in result)


def test_scan_skips_underscore_files(tmp_path: Path):
    watch = tmp_path / "clips"
    watch.mkdir()
    (watch / "_context.md").write_text("context\n", encoding="utf-8")
    (watch / "real.md").write_text("# Real\n", encoding="utf-8")

    with patch("llmwiki.web_clipper.REPO_ROOT", tmp_path):
        result = scan_for_clips(
            config={
                "web_clipper": {
                    "enabled": True,
                    "watch_dir": str(watch),
                }
            },
            queue_file=tmp_path / "q.json",
        )
    assert len(result) == 1


def test_scan_auto_queues(tmp_path: Path):
    """New files are auto-added to the ingest queue."""
    watch = tmp_path / "clips"
    watch.mkdir()
    (watch / "article.md").write_text("# Art\n", encoding="utf-8")
    qf = tmp_path / "q.json"

    with patch("llmwiki.web_clipper.REPO_ROOT", tmp_path):
        scan_for_clips(
            config={
                "web_clipper": {
                    "enabled": True,
                    "watch_dir": str(watch),
                    "auto_queue": True,
                }
            },
            queue_file=qf,
        )

    queued = peek(queue_file=qf)
    assert len(queued) == 1


def test_scan_no_auto_queue(tmp_path: Path):
    """auto_queue=False means files found but not queued."""
    watch = tmp_path / "clips"
    watch.mkdir()
    (watch / "article.md").write_text("# Art\n", encoding="utf-8")
    qf = tmp_path / "q.json"

    with patch("llmwiki.web_clipper.REPO_ROOT", tmp_path):
        result = scan_for_clips(
            config={
                "web_clipper": {
                    "enabled": True,
                    "watch_dir": str(watch),
                    "auto_queue": False,
                }
            },
            queue_file=qf,
        )

    assert len(result) == 1
    queued = peek(queue_file=qf)
    assert len(queued) == 0  # not queued


def test_scan_deduplicates_with_existing_queue(tmp_path: Path):
    """Already-queued files are not returned again."""
    watch = tmp_path / "clips"
    watch.mkdir()
    (watch / "old.md").write_text("# Old\n", encoding="utf-8")
    (watch / "new.md").write_text("# New\n", encoding="utf-8")
    qf = tmp_path / "q.json"

    with patch("llmwiki.web_clipper.REPO_ROOT", tmp_path):
        # First scan queues both
        scan_for_clips(
            config={"web_clipper": {"enabled": True, "watch_dir": str(watch)}},
            queue_file=qf,
        )
        # Second scan finds nothing new
        result = scan_for_clips(
            config={"web_clipper": {"enabled": True, "watch_dir": str(watch)}},
            queue_file=qf,
        )
    assert result == []


def test_scan_empty_dir(tmp_path: Path):
    watch = tmp_path / "clips"
    watch.mkdir()

    with patch("llmwiki.web_clipper.REPO_ROOT", tmp_path):
        result = scan_for_clips(
            config={"web_clipper": {"enabled": True, "watch_dir": str(watch)}},
            queue_file=tmp_path / "q.json",
        )
    assert result == []
