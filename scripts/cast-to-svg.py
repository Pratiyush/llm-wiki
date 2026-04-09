#!/usr/bin/env python3
"""Convert an asciinema v2 .cast file into an animated SVG.

Reads docs/demo.cast and writes docs/demo.svg.

The SVG uses CSS @keyframes to show/hide terminal frames at the correct
timestamps.  No external dependencies — Python 3.9+ stdlib only.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SVG_W, SVG_H = 800, 500
PADDING = 20
FONT_SIZE = 13
LINE_HEIGHT = 18
COLS = 100  # terminal columns (from header)

# Catppuccin-ish palette
BG = "#1e1e2e"
FG = "#cdd6f4"
GREEN = "#a6e3a1"
CYAN = "#89b4fa"
YELLOW = "#f9e2af"
DIM = "#6c7086"

# Frame sampling — merge events that are within MERGE_GAP seconds.
# This avoids creating a separate SVG frame for every single keystroke.
MERGE_GAP = 0.08  # seconds

# Maximum visible lines in the terminal viewport
MAX_LINES = int((SVG_H - 2 * PADDING - 30) / LINE_HEIGHT)  # reserve 30px for title bar

ROOT = Path(__file__).resolve().parent.parent
CAST_PATH = ROOT / "docs" / "demo.cast"
SVG_PATH = ROOT / "docs" / "demo.svg"


# ---------------------------------------------------------------------------
# ANSI handling
# ---------------------------------------------------------------------------
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?(?:\x07|\x1b\\)|\x1b\[[\?0-9;]*[hl]")


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from *text*."""
    return _ANSI_RE.sub("", text)


# Simple ANSI SGR colour parser — we only care about bold+fg for colourising
# the SVG output.  Returns a list of (text, colour) segments.
_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")


def parse_ansi_segments(text: str) -> list[tuple[str, str]]:
    """Split *text* into (plain_text, css_colour) segments."""
    segments: list[tuple[str, str]] = []
    colour = FG
    bold = False
    pos = 0
    for m in _SGR_RE.finditer(text):
        # Text before this escape
        before = text[pos:m.start()]
        # Strip any non-SGR escapes from this chunk
        before = re.sub(r"\x1b\[[0-9;]*[A-HJKSTfn]|\x1b\[[\?0-9;]*[hl]|\x1b\].*?(?:\x07|\x1b\\)", "", before)
        if before:
            segments.append((before, colour))
        pos = m.end()
        # Parse the SGR codes
        codes = [int(c) if c else 0 for c in m.group(1).split(";")]
        for code in codes:
            if code == 0:
                colour = FG
                bold = False
            elif code == 1:
                bold = True
            elif code == 4:
                pass  # underline — ignore for colour
            elif code == 32:
                colour = GREEN
            elif code == 33:
                colour = YELLOW
            elif code == 36:
                colour = CYAN
            elif code == 39:
                colour = FG
    # Remaining text
    remaining = text[pos:]
    remaining = re.sub(r"\x1b\[[0-9;]*[A-HJKSTfn]|\x1b\[[\?0-9;]*[hl]|\x1b\].*?(?:\x07|\x1b\\)", "", remaining)
    if remaining:
        segments.append((remaining, colour))
    return segments


# ---------------------------------------------------------------------------
# Cast parsing
# ---------------------------------------------------------------------------

def load_cast(path: Path) -> tuple[dict, list[tuple[float, str]]]:
    """Return (header, [(timestamp, output_text), ...])."""
    lines = path.read_text().splitlines()
    header = json.loads(lines[0])
    events: list[tuple[float, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        ts, _typ, data = json.loads(line)
        events.append((float(ts), data))
    return header, events


# ---------------------------------------------------------------------------
# Build terminal snapshots (frames)
# ---------------------------------------------------------------------------

def build_frames(events: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Replay events into a virtual screen buffer, snapshotting at boundaries.

    Returns [(timestamp, full_screen_text), ...] where full_screen_text
    contains the raw ANSI codes (we parse them later for colouring).
    """
    # Simple line-buffer approach: we accumulate text, split on \r\n.
    # \x1b[2J\x1b[H = clear screen.
    buffer = ""  # accumulated raw output
    frames: list[tuple[float, str]] = []
    last_ts = -999.0

    for ts, data in events:
        # Handle clear-screen escape
        if "\x1b[2J" in data or "\x1b[H" in data:
            data = data.replace("\x1b[2J", "").replace("\x1b[H", "")
            buffer = ""

        buffer += data

        # Merge rapid-fire events (typing individual characters)
        if ts - last_ts < MERGE_GAP:
            # Update the last frame in-place rather than adding a new one
            if frames:
                frames[-1] = (ts, buffer)
                continue

        frames.append((ts, buffer))
        last_ts = ts

    return frames


def screen_lines(raw: str) -> list[str]:
    """Split accumulated raw output into display lines."""
    # Normalise line endings
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    # Remove trailing empty line if present
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


# ---------------------------------------------------------------------------
# SVG generation
# ---------------------------------------------------------------------------

def render_line_svg(line: str, x: float, y: float) -> str:
    """Render one terminal line as an SVG <text> element with coloured <tspan>s."""
    segments = parse_ansi_segments(line)
    if not segments:
        return ""

    parts: list[str] = []
    parts.append(f'<text x="{x}" y="{y}" class="t">')
    for text, colour in segments:
        escaped = html.escape(text)
        if colour == FG:
            parts.append(f"<tspan>{escaped}</tspan>")
        else:
            parts.append(f'<tspan fill="{colour}">{escaped}</tspan>')
    parts.append("</text>")
    return "".join(parts)


def generate_svg(frames: list[tuple[float, str]]) -> str:
    """Build the complete SVG string from terminal frames."""
    total_duration = frames[-1][0] + 3.0  # 3s pause before loop

    # ---- Keyframes CSS ----
    # Each frame is visible for its window, hidden otherwise.
    css_parts: list[str] = []
    css_parts.append(f"""\
    <style>
      .term-bg {{ fill: {BG}; }}
      .t {{ font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', 'Menlo', monospace;
            font-size: {FONT_SIZE}px; fill: {FG}; white-space: pre; }}
      .title-bar {{ fill: #313244; }}
      .title-text {{ font-family: -apple-system, 'Segoe UI', sans-serif;
                     font-size: 12px; fill: #a6adc8; }}
      .dot {{ r: 6; }}
      .dot-r {{ fill: #f38ba8; }}
      .dot-y {{ fill: #f9e2af; }}
      .dot-g {{ fill: #a6e3a1; }}
      .frame {{ opacity: 0; }}
""")

    for i, (ts, _raw) in enumerate(frames):
        if i + 1 < len(frames):
            next_ts = frames[i + 1][0]
        else:
            next_ts = total_duration

        start_pct = (ts / total_duration) * 100
        end_pct = (next_ts / total_duration) * 100
        # Tiny fade: visible from start to end, hidden otherwise
        anim_name = f"f{i}"
        # Ensure percentages are clamped
        s = max(0, min(start_pct, 100))
        e = max(0, min(end_pct, 100))

        css_parts.append(f"      @keyframes {anim_name} {{")
        if s > 0:
            css_parts.append(f"        0% {{ opacity: 0; }}")
        css_parts.append(f"        {s:.4f}% {{ opacity: 1; }}")
        css_parts.append(f"        {e:.4f}% {{ opacity: 1; }}")
        if e < 100:
            css_parts.append(f"        {e + 0.001:.4f}% {{ opacity: 0; }}")
            css_parts.append(f"        100% {{ opacity: 0; }}")
        else:
            css_parts.append(f"        100% {{ opacity: 1; }}")
        css_parts.append(f"      }}")
        css_parts.append(
            f"      .frame-{i} {{ animation: {anim_name} {total_duration:.2f}s linear infinite; }}"
        )

    css_parts.append("    </style>")
    css_block = "\n".join(css_parts)

    # ---- SVG body ----
    svg_parts: list[str] = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_W} {SVG_H}" '
        f'width="{SVG_W}" height="{SVG_H}">'
    )
    svg_parts.append(css_block)

    # Background
    svg_parts.append(f'  <rect width="{SVG_W}" height="{SVG_H}" rx="10" class="term-bg"/>')

    # Title bar
    title_bar_h = 30
    svg_parts.append(
        f'  <rect width="{SVG_W}" height="{title_bar_h}" rx="10" class="title-bar"/>'
    )
    svg_parts.append(
        f'  <rect x="0" y="20" width="{SVG_W}" height="10" class="title-bar"/>'
    )
    # Traffic lights
    svg_parts.append(f'  <circle cx="20" cy="15" class="dot dot-r"/>')
    svg_parts.append(f'  <circle cx="38" cy="15" class="dot dot-y"/>')
    svg_parts.append(f'  <circle cx="56" cy="15" class="dot dot-g"/>')
    # Title
    svg_parts.append(
        f'  <text x="{SVG_W // 2}" y="19" text-anchor="middle" class="title-text">'
        f"llm-wiki demo</text>"
    )

    content_y_start = title_bar_h + PADDING - 5

    # ---- Frames ----
    for i, (ts, raw) in enumerate(frames):
        lines = screen_lines(raw)
        # Show only the tail that fits in the viewport
        if len(lines) > MAX_LINES:
            lines = lines[-MAX_LINES:]

        svg_parts.append(f'  <g class="frame frame-{i}">')
        # Opaque background to cover previous frames
        svg_parts.append(
            f'    <rect x="0" y="{title_bar_h}" width="{SVG_W}" '
            f'height="{SVG_H - title_bar_h}" class="term-bg"/>'
        )
        for li, line in enumerate(lines):
            y = content_y_start + li * LINE_HEIGHT
            rendered = render_line_svg(line, PADDING, y)
            if rendered:
                svg_parts.append(f"    {rendered}")
        svg_parts.append("  </g>")

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


# ---------------------------------------------------------------------------
# Thin frames by dropping near-duplicates
# ---------------------------------------------------------------------------

def thin_frames(frames: list[tuple[float, str]], max_frames: int = 120) -> list[tuple[float, str]]:
    """Reduce frame count by merging frames whose visible text hasn't changed."""
    if not frames:
        return frames
    thinned: list[tuple[float, str]] = [frames[0]]
    prev_text = strip_ansi(frames[0][1])
    for ts, raw in frames[1:]:
        cur_text = strip_ansi(raw)
        if cur_text == prev_text:
            # Same visual content — just update the timestamp of the last kept frame
            continue
        thinned.append((ts, raw))
        prev_text = cur_text

    # If still too many, sample uniformly but always keep first and last
    if len(thinned) > max_frames:
        step = len(thinned) / max_frames
        sampled = []
        idx = 0.0
        while int(idx) < len(thinned):
            sampled.append(thinned[int(idx)])
            idx += step
        if sampled[-1] != thinned[-1]:
            sampled.append(thinned[-1])
        thinned = sampled

    return thinned


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not CAST_PATH.exists():
        print(f"Error: {CAST_PATH} not found", file=sys.stderr)
        sys.exit(1)

    header, events = load_cast(CAST_PATH)
    print(f"Loaded {len(events)} events from {CAST_PATH.name} "
          f"({header.get('width', '?')}x{header.get('height', '?')}, "
          f'"{header.get("title", "")}")')

    frames = build_frames(events)
    print(f"Built {len(frames)} raw frames")

    frames = thin_frames(frames)
    print(f"Thinned to {len(frames)} unique frames")

    svg = generate_svg(frames)

    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(svg)
    size_kb = SVG_PATH.stat().st_size / 1024
    print(f"Wrote {SVG_PATH} ({size_kb:.0f} KB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
