"""Tests for the configurable build/lint schedule (v1.0, #157)."""

from __future__ import annotations

import pytest

from llmwiki.cli import _should_run_after_sync, _load_schedule_config


def test_on_sync_triggers():
    assert _should_run_after_sync("on-sync") is True


def test_manual_does_not_trigger():
    assert _should_run_after_sync("manual") is False


def test_daily_does_not_trigger_from_sync():
    """Daily schedule runs from a scheduled task, not from sync."""
    assert _should_run_after_sync("daily") is False


def test_weekly_does_not_trigger_from_sync():
    assert _should_run_after_sync("weekly") is False


def test_never_does_not_trigger():
    assert _should_run_after_sync("never") is False


def test_case_insensitive():
    assert _should_run_after_sync("ON-SYNC") is True
    assert _should_run_after_sync("Manual") is False


def test_unknown_schedule_does_not_trigger():
    assert _should_run_after_sync("bogus") is False


def test_empty_string_does_not_trigger():
    assert _should_run_after_sync("") is False


def test_load_schedule_config_defaults():
    """When no config, should return sensible defaults."""
    config = _load_schedule_config()
    # Actual config may or may not exist; confirm the shape is right
    assert "build" in config
    assert "lint" in config
    assert isinstance(config["build"], str)
    assert isinstance(config["lint"], str)
