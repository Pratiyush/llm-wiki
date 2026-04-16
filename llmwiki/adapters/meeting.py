"""Meeting transcript adapter (v1.0 · #146).

Discovers VTT, SRT, and plain-text transcript files and converts them
to frontmatter-tagged markdown for ingestion into the wiki.

Parsing:
  - **VTT**: WebVTT format with optional speaker tags (``<v Speaker>``)
  - **SRT**: SubRip format with numbered cue blocks
  - **TXT**: Plain text treated as a single block

The output markdown includes:
  - YAML frontmatter (title, type, tags, date, source_file, project)
  - Speaker-tagged conversation sections
  - Extracted key decisions (lines containing "decision", "agreed", "action item")

Configuration (in ``sessions_config.json``):
  - ``meeting.enabled``: bool (default: false — opt-in)
  - ``meeting.source_dirs``: list of paths to scan
  - ``meeting.extensions``: list of file extensions (default: [".vtt", ".srt"])
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("meeting")
class MeetingAdapter(BaseAdapter):
    """Meeting transcript adapter — VTT, SRT, and plain-text transcripts."""

    session_store_path: Path | list[Path] = Path("~/meetings")

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        mc = (config or {}).get("meeting", {})
        self._enabled = mc.get("enabled", False)
        self._extensions = mc.get("extensions", [".vtt", ".srt"])
        dirs = mc.get("source_dirs", [])
        if dirs:
            self.session_store_path = [Path(d) for d in dirs]

    @classmethod
    def is_available(cls) -> bool:
        # Disabled by default — user must opt in via config
        return False

    def is_available_with_config(self) -> bool:
        """Check availability using instance config."""
        if not self._enabled:
            return False
        paths = self.session_store_path
        if isinstance(paths, Path):
            paths = [paths]
        return any(Path(p).expanduser().exists() for p in paths)

    def discover_sessions(self) -> list[Path]:
        """Discover transcript files matching configured extensions."""
        paths: list[Path] = []
        stores = self.session_store_path
        if isinstance(stores, Path):
            stores = [stores]
        for store in stores:
            store = Path(store).expanduser()
            if store.exists():
                for ext in self._extensions:
                    paths.extend(sorted(store.rglob(f"*{ext}")))
        return paths


# ─── VTT parsing ───────────────────────────────────────────────────────

_VTT_TIMESTAMP = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
)
_VTT_SPEAKER = re.compile(r"<v\s+([^>]+)>(.+?)(?:</v>)?$")


def parse_vtt(text: str) -> list[dict[str, str]]:
    """Parse a WebVTT file into a list of cue dicts.

    Each dict has: ``speaker`` (or ""), ``text``, ``start``, ``end``.
    """
    cues: list[dict[str, str]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = _VTT_TIMESTAMP.match(line)
        if m:
            start = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
            end = f"{m.group(5)}:{m.group(6)}:{m.group(7)}"
            i += 1
            # Collect content lines until blank
            content_lines: list[str] = []
            while i < len(lines) and lines[i].strip():
                content_lines.append(lines[i].strip())
                i += 1
            content = " ".join(content_lines)
            # Check for speaker tag
            sm = _VTT_SPEAKER.match(content)
            if sm:
                cues.append({
                    "speaker": sm.group(1).strip(),
                    "text": sm.group(2).strip(),
                    "start": start,
                    "end": end,
                })
            else:
                cues.append({
                    "speaker": "",
                    "text": content,
                    "start": start,
                    "end": end,
                })
        else:
            i += 1
    return cues


# ─── SRT parsing ──────────────────────────────────────────────────────

_SRT_TIMESTAMP = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def parse_srt(text: str) -> list[dict[str, str]]:
    """Parse an SRT file into a list of cue dicts."""
    cues: list[dict[str, str]] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue
        # Find the timestamp line
        for j, line in enumerate(lines):
            m = _SRT_TIMESTAMP.match(line.strip())
            if m:
                start = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
                end = f"{m.group(5)}:{m.group(6)}:{m.group(7)}"
                content = " ".join(l.strip() for l in lines[j + 1:] if l.strip())
                cues.append({
                    "speaker": "",
                    "text": content,
                    "start": start,
                    "end": end,
                })
                break
    return cues


# ─── Markdown rendering ──────────────────────────────────────────────

_DECISION_PATTERNS = re.compile(
    r"(?i)(decision|decided|agreed|action item|next step|follow.?up|TODO)",
)


def extract_decisions(cues: list[dict[str, str]]) -> list[str]:
    """Extract lines that look like decisions or action items."""
    return [
        cue["text"]
        for cue in cues
        if _DECISION_PATTERNS.search(cue["text"])
    ]


def render_transcript_markdown(
    cues: list[dict[str, str]],
    source_path: Path,
    project: str = "meetings",
) -> str:
    """Render parsed cues into frontmatter-tagged markdown."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    # Group by speaker for readability
    speakers = sorted(set(c["speaker"] for c in cues if c["speaker"]))
    decisions = extract_decisions(cues)

    title = source_path.stem.replace("-", " ").replace("_", " ").title()

    fm = [
        "---",
        f'title: "{title}"',
        "type: source",
        f"tags: [meeting, transcript]",
        f"date: {date_str}",
        f"source_file: {source_path}",
        f"project: {project}",
        f"speakers: [{', '.join(speakers)}]" if speakers else "speakers: []",
        f"cue_count: {len(cues)}",
        "---",
        "",
        f"# {title}",
        "",
    ]

    # Speakers section
    if speakers:
        fm.append("## Speakers")
        fm.append("")
        for s in speakers:
            fm.append(f"- **{s}**")
        fm.append("")

    # Decisions section
    if decisions:
        fm.append("## Key Decisions & Action Items")
        fm.append("")
        for d in decisions:
            fm.append(f"- {d}")
        fm.append("")

    # Transcript section
    fm.append("## Transcript")
    fm.append("")
    current_speaker = None
    for cue in cues:
        if cue["speaker"] and cue["speaker"] != current_speaker:
            current_speaker = cue["speaker"]
            fm.append(f"**{current_speaker}** ({cue['start']}):")
            fm.append("")
        fm.append(f"{cue['text']}")
        fm.append("")

    return "\n".join(fm)
