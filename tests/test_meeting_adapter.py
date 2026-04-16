"""Tests for the meeting transcript adapter (v1.0, #146)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.adapters.meeting import (
    MeetingAdapter,
    parse_vtt,
    parse_srt,
    extract_decisions,
    render_transcript_markdown,
)

# ─── VTT fixtures ──────────────────────────────────────────────────────

SAMPLE_VTT = """\
WEBVTT

00:00:01.000 --> 00:00:04.000
<v Alice>Hello everyone, let's start the standup.

00:00:04.500 --> 00:00:08.000
<v Bob>Sure. I worked on the API refactor yesterday.

00:00:08.500 --> 00:00:12.000
<v Alice>Great. The decision is to ship the refactor by Friday.

00:00:12.500 --> 00:00:15.000
Next action item: Bob to write tests.
"""

SAMPLE_SRT = """\
1
00:00:01,000 --> 00:00:04,000
Hello everyone, let's start.

2
00:00:04,500 --> 00:00:08,000
I agreed to handle the deployment.

3
00:00:08,500 --> 00:00:12,000
Next follow-up is on Monday.
"""


# ─── VTT parsing ──────────────────────────────────────────────────────


def test_parse_vtt_basic():
    cues = parse_vtt(SAMPLE_VTT)
    assert len(cues) >= 3


def test_parse_vtt_speaker_extraction():
    cues = parse_vtt(SAMPLE_VTT)
    speakers = [c["speaker"] for c in cues if c["speaker"]]
    assert "Alice" in speakers
    assert "Bob" in speakers


def test_parse_vtt_timestamps():
    cues = parse_vtt(SAMPLE_VTT)
    assert cues[0]["start"] == "00:00:01"
    assert cues[0]["end"] == "00:00:04"


def test_parse_vtt_no_speaker():
    cues = parse_vtt(SAMPLE_VTT)
    # Last cue has no speaker tag
    no_speaker = [c for c in cues if not c["speaker"]]
    assert len(no_speaker) >= 1


def test_parse_vtt_empty():
    assert parse_vtt("") == []
    assert parse_vtt("WEBVTT\n\n") == []


# ─── SRT parsing ──────────────────────────────────────────────────────


def test_parse_srt_basic():
    cues = parse_srt(SAMPLE_SRT)
    assert len(cues) == 3


def test_parse_srt_timestamps():
    cues = parse_srt(SAMPLE_SRT)
    assert cues[0]["start"] == "00:00:01"


def test_parse_srt_text():
    cues = parse_srt(SAMPLE_SRT)
    assert "Hello everyone" in cues[0]["text"]


def test_parse_srt_empty():
    assert parse_srt("") == []


def test_parse_srt_malformed_block():
    # Single line without timestamp
    assert parse_srt("just text\n") == []


# ─── Decision extraction ─────────────────────────────────────────────


def test_extract_decisions_from_vtt():
    cues = parse_vtt(SAMPLE_VTT)
    decisions = extract_decisions(cues)
    assert len(decisions) >= 2  # "decision" and "action item"


def test_extract_decisions_none():
    cues = [{"speaker": "A", "text": "Just chatting", "start": "0", "end": "1"}]
    assert extract_decisions(cues) == []


def test_extract_decisions_case_insensitive():
    cues = [{"speaker": "", "text": "We DECIDED to go with React", "start": "0", "end": "1"}]
    decisions = extract_decisions(cues)
    assert len(decisions) == 1


# ─── Markdown rendering ──────────────────────────────────────────────


def test_render_has_frontmatter():
    cues = parse_vtt(SAMPLE_VTT)
    md = render_transcript_markdown(cues, Path("meeting.vtt"))
    assert md.startswith("---\n")
    assert "type: source" in md
    assert "tags: [meeting, transcript]" in md


def test_render_has_speakers_section():
    cues = parse_vtt(SAMPLE_VTT)
    md = render_transcript_markdown(cues, Path("meeting.vtt"))
    assert "## Speakers" in md
    assert "**Alice**" in md
    assert "**Bob**" in md


def test_render_has_decisions_section():
    cues = parse_vtt(SAMPLE_VTT)
    md = render_transcript_markdown(cues, Path("meeting.vtt"))
    assert "## Key Decisions" in md


def test_render_has_transcript_section():
    cues = parse_vtt(SAMPLE_VTT)
    md = render_transcript_markdown(cues, Path("meeting.vtt"))
    assert "## Transcript" in md


def test_render_empty_cues():
    md = render_transcript_markdown([], Path("empty.vtt"))
    assert "---" in md
    assert "## Transcript" in md
    assert "## Speakers" not in md  # no speakers


def test_render_project_in_frontmatter():
    cues = parse_vtt(SAMPLE_VTT)
    md = render_transcript_markdown(cues, Path("m.vtt"), project="my-team")
    assert "project: my-team" in md


# ─── Adapter class ────────────────────────────────────────────────────


def test_adapter_not_available_by_default():
    assert MeetingAdapter.is_available() is False


def test_adapter_with_config(tmp_path: Path):
    meetings_dir = tmp_path / "meetings"
    meetings_dir.mkdir()
    (meetings_dir / "standup.vtt").write_text(SAMPLE_VTT, encoding="utf-8")

    adapter = MeetingAdapter(config={
        "meeting": {
            "enabled": True,
            "source_dirs": [str(meetings_dir)],
        }
    })
    assert adapter.is_available_with_config() is True
    sessions = adapter.discover_sessions()
    assert len(sessions) == 1
    assert sessions[0].name == "standup.vtt"


def test_adapter_disabled_by_config(tmp_path: Path):
    adapter = MeetingAdapter(config={"meeting": {"enabled": False}})
    assert adapter.is_available_with_config() is False
