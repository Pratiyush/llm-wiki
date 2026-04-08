"""Tool-calling bar chart (v0.8 — closes #65).

Pure-SVG horizontal bar chart, stdlib-only. Consumes the `tool_counts`
dict that the converter writes into session frontmatter (#63) and renders
a compact "Tools used in this session" card.

Design notes:

* **Horizontal** — tool names are long ("mcp__Claude_Preview__preview_start")
  and horizontal bars give the labels room without wrapping.
* **Descending sort** — the tool that dominates a session should be the
  first thing you see. A "Other (N tools)" row summarises overflow.
* **Category palette** — each tool bucket gets a deliberate color so the
  eye can tell I/O vs search vs execution vs network vs planning at a
  glance. Full list at the top of the module — easy to extend when new
  MCP tools appear in real transcripts.
* **No grid lines, no axis ticks** — only the bar label + count, per
  Tufte. Absolute counts go on each bar; percentages go in the tooltip.
* **CSS custom properties** drive the final colors so the page theme
  can override via `--tool-cat-*` vars. Fallback hex lives in an inline
  `<style>` block in the SVG.
* Up to `max_bars` visible bars (default 10). If there are more tools,
  the rest collapse into a single "Other (N tools)" row so the chart
  stays readable.
"""

from __future__ import annotations

import html
import json
from typing import Mapping, Optional

# ─── layout constants ────────────────────────────────────────────────────

BAR_HEIGHT = 18
BAR_GAP = 6
LABEL_WIDTH = 170  # room for tool name on the left
COUNT_WIDTH = 52   # room for the count text on the right
BAR_MAX_WIDTH = 300
LEFT_PAD = 6
RIGHT_PAD = 6
TOP_PAD = 6


# ─── category palette ────────────────────────────────────────────────────

# Ordered: first match wins. Prefix match (tool name startswith(pattern))
# or exact match.
_TOOL_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    # (category_name, (patterns…))
    ("io", (
        "Read", "Write", "Edit", "NotebookEdit", "MultiEdit",
    )),
    ("search", (
        "Grep", "Glob", "WebSearch", "ToolSearch",
    )),
    ("exec", (
        "Bash", "TaskOutput", "TaskStop", "Skill",
    )),
    ("network", (
        "WebFetch", "mcp__",
    )),
    ("plan", (
        "Agent", "AskUserQuestion", "TodoWrite", "ExitPlanMode",
        "CronCreate", "CronDelete", "CronList", "EnterPlanMode",
        "EnterWorktree", "ExitWorktree",
    )),
]

_CATEGORY_PALETTE = {
    "io":      "#3b82f6",  # blue
    "search":  "#a855f7",  # purple
    "exec":    "#f97316",  # orange
    "network": "#10b981",  # green
    "plan":    "#64748b",  # slate
    "other":   "#9ca3af",  # gray
}


def _category_for(tool_name: str) -> str:
    """Return the category key for a given tool name. Defaults to 'other'."""
    for cat, patterns in _TOOL_CATEGORIES:
        for p in patterns:
            if tool_name == p or tool_name.startswith(p):
                return cat
    return "other"


# ─── data collection ─────────────────────────────────────────────────────


def parse_tool_counts(meta: Mapping[str, object]) -> dict[str, int]:
    """Pull `tool_counts` out of a session meta dict.

    The converter (#63) serializes `tool_counts` as an inline JSON object
    in frontmatter; the llmwiki frontmatter parser stores it as a plain
    string, so we `json.loads` it here. Missing / malformed values return
    an empty dict so callers don't have to null-check.
    """
    raw = meta.get("tool_counts")
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return {str(k): int(v) for k, v in raw.items() if isinstance(v, (int, float))}
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            return {}
        if isinstance(data, dict):
            return {str(k): int(v) for k, v in data.items()
                    if isinstance(v, (int, float))}
    return {}


def aggregate_tool_counts(metas: list[Mapping[str, object]]) -> dict[str, int]:
    """Sum `tool_counts` across many sessions.

    Used to build a project-level aggregate by feeding in every session's
    meta dict from the group. Tool names are preserved verbatim (including
    namespace prefixes like `mcp__Claude_in_Chrome__*`) so the categorisation
    can still differentiate them.
    """
    out: dict[str, int] = {}
    for meta in metas:
        for name, count in parse_tool_counts(meta).items():
            if count <= 0:
                continue
            out[name] = out.get(name, 0) + count
    return out


# ─── SVG render ──────────────────────────────────────────────────────────


def render_tool_chart(
    counts: dict[str, int],
    max_bars: int = 10,
    title: Optional[str] = None,
) -> str:
    """Render a horizontal bar chart as a self-contained `<svg>`.

    Empty input returns an empty string so callers can `if chart:` gate
    on whether to render the surrounding card at all. The returned SVG
    uses CSS custom properties `--tool-cat-io`, `--tool-cat-search`, etc.
    with hex fallbacks so it degrades gracefully outside a styled host.
    """
    # Filter out zero counts and sort descending.
    items = [(name, c) for name, c in counts.items() if c > 0]
    if not items:
        return ""
    items.sort(key=lambda x: (-x[1], x[0]))

    total = sum(c for _, c in items)

    # Overflow collapse
    visible = items[:max_bars]
    hidden_count = len(items) - len(visible)
    if hidden_count > 0:
        hidden_total = sum(c for _, c in items[max_bars:])
        visible.append((f"Other ({hidden_count} tools)", hidden_total))

    max_count = max(c for _, c in visible)
    n_bars = len(visible)
    inner_h = n_bars * BAR_HEIGHT + (n_bars - 1) * BAR_GAP
    total_w = LEFT_PAD + LABEL_WIDTH + BAR_MAX_WIDTH + COUNT_WIDTH + RIGHT_PAD
    total_h = TOP_PAD * 2 + inner_h

    label = title or "Tool calls by tool"

    parts: list[str] = [
        f'<svg class="tool-chart-svg" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {total_w} {total_h}" '
        f'width="{total_w}" height="{total_h}" '
        f'role="img" aria-label="{html.escape(label)}">',
        '<style>',
        '.tool-chart-svg text { font: 11px system-ui, -apple-system, sans-serif; fill: var(--text, #0f172a); }',
        '.tool-chart-svg .label-text { font-weight: 500; text-anchor: end; }',
        '.tool-chart-svg .count-text { fill: var(--text-secondary, #475569); }',
    ]
    for cat, fallback in _CATEGORY_PALETTE.items():
        parts.append(
            f'.tool-chart-svg .cat-{cat} {{ fill: var(--tool-cat-{cat}, {fallback}); }}'
        )
    parts.append('</style>')

    for idx, (name, count) in enumerate(visible):
        y = TOP_PAD + idx * (BAR_HEIGHT + BAR_GAP)
        # Label on the left, right-aligned
        label_x = LEFT_PAD + LABEL_WIDTH - 6
        parts.append(
            f'<text class="label-text" x="{label_x}" y="{y + BAR_HEIGHT - 5}">'
            f'{html.escape(_shorten(name))}</text>'
        )
        # Bar
        bar_x = LEFT_PAD + LABEL_WIDTH
        bar_w = max(1, round(count / max_count * BAR_MAX_WIDTH))
        category = (
            "other" if name.startswith("Other (") else _category_for(name)
        )
        pct = 100.0 * count / total if total > 0 else 0.0
        tooltip = f"{name}: {count} call{'s' if count != 1 else ''} ({pct:.1f}%)"
        parts.append(
            f'<rect class="cat-{category}" x="{bar_x}" y="{y}" '
            f'width="{bar_w}" height="{BAR_HEIGHT}" rx="2" ry="2">'
            f'<title>{html.escape(tooltip)}</title>'
            f'</rect>'
        )
        # Count text to the right of the bar
        count_x = bar_x + bar_w + 6
        parts.append(
            f'<text class="count-text" x="{count_x}" y="{y + BAR_HEIGHT - 5}">'
            f'{count}</text>'
        )

    parts.append('</svg>')
    return "\n".join(parts)


def _shorten(name: str, max_len: int = 28) -> str:
    """Trim long tool names so they fit in the label column."""
    if len(name) <= max_len:
        return name
    return name[: max_len - 1] + "…"


# ─── convenience: all-in-one render helpers ─────────────────────────────


def render_session_tool_chart(meta: Mapping[str, object]) -> str:
    """Render a tool chart for a single session. Returns empty string if
    the session has no recorded tool calls."""
    return render_tool_chart(parse_tool_counts(meta), title="Tool calls in this session")


def render_project_tool_chart(metas: list[Mapping[str, object]], project_slug: str) -> str:
    """Render an aggregate tool chart for all sessions in a project."""
    return render_tool_chart(
        aggregate_tool_counts(metas),
        title=f"Tool calls across all {project_slug} sessions",
    )
