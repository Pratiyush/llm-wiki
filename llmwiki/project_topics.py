"""Project topics — GitHub-style tag chips on project cards + pages.

Surfaces user-declared topic tags on the home page project cards, the
per-project detail page, the projects index, and (as filterable chips)
the sessions index. The same "topics" concept GitHub shows at the top
of a repo page, so visitors can instantly see what a project is about.

Data sources, in order of precedence:

1. **Explicit**: `wiki/projects/<slug>.md` frontmatter. Users drop a
   small file per project with `topics: [rust, blog, ssg]` and an
   optional `description` + `homepage` URL. This is the primary
   source — it's user-curated and stable.

2. **Fallback**: session `tags:` frontmatter, aggregated across every
   session in the project, with the universal noise tags
   (`claude-code`, `session-transcript`, `demo`) filtered out. Sessions
   rarely carry distinctive tags today, but this makes the feature
   zero-config for projects where the user has added project-specific
   tags to their sessions.

Missing data gracefully returns an empty list — callers decide whether
to render the empty state.

Stdlib-only.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, TypedDict

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

# Tags that appear on nearly every session and carry no
# project-specific signal. Filtered out of the session-tag fallback.
_NOISE_TAGS: frozenset[str] = frozenset(
    {"claude-code", "session-transcript", "demo", "codex-cli", "cursor"}
)


class ProjectTopicsProfile(TypedDict, total=False):
    """Explicit metadata for a project, loaded from
    `wiki/projects/<slug>.md` frontmatter."""
    topics: list[str]
    description: str
    homepage: str


def _parse_topics_frontmatter(text: str) -> dict[str, Any]:
    """Tiny frontmatter parser — mirrors build.py's but self-contained
    so this module can be tested in isolation. Supports plain key/value
    and bracketed-list values."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    raw = m.group(1)
    meta: dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key.strip()] = (
                [x.strip() for x in inner.split(",") if x.strip()]
                if inner else []
            )
        else:
            meta[key.strip()] = value
    return meta


def load_project_profile(
    projects_dir: Path,
    project_slug: str,
) -> Optional[ProjectTopicsProfile]:
    """Load `<projects_dir>/<slug>.md` and extract the topics profile.

    Returns `None` if the file doesn't exist. Missing fields are
    omitted from the result dict.
    """
    path = projects_dir / f"{project_slug}.md"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta = _parse_topics_frontmatter(text)
    profile: ProjectTopicsProfile = {}
    topics = meta.get("topics")
    if isinstance(topics, list):
        # Normalize: strip, lowercase, dedup, keep order
        seen: set[str] = set()
        normalized: list[str] = []
        for t in topics:
            t_clean = str(t).strip().lower()
            if t_clean and t_clean not in seen:
                seen.add(t_clean)
                normalized.append(t_clean)
        profile["topics"] = normalized
    elif isinstance(topics, str) and topics:
        profile["topics"] = [t.strip().lower() for t in topics.strip("[]").split(",") if t.strip()]
    description = meta.get("description")
    if description:
        profile["description"] = str(description)
    homepage = meta.get("homepage")
    if homepage:
        profile["homepage"] = str(homepage)
    return profile


def extract_session_topics(
    session_metas: Iterable[Mapping[str, Any]],
    max_topics: int = 8,
    min_count: int = 2,
) -> list[str]:
    """Aggregate tags across a project's sessions and return the most
    common non-noise tags. Used as a fallback when there's no explicit
    `wiki/projects/<slug>.md` profile.

    A tag must appear in at least `min_count` sessions to be included —
    filters out one-off stragglers. Returns at most `max_topics` tags,
    ordered by frequency descending.
    """
    counts: Counter[str] = Counter()
    for meta in session_metas:
        raw = meta.get("tags")
        if isinstance(raw, list):
            for t in raw:
                tag = str(t).strip().lower()
                if tag and tag not in _NOISE_TAGS:
                    counts[tag] += 1
        elif isinstance(raw, str) and raw:
            for t in raw.strip("[]").split(","):
                tag = t.strip().lower()
                if tag and tag not in _NOISE_TAGS:
                    counts[tag] += 1
    filtered = [(tag, c) for tag, c in counts.items() if c >= min_count]
    filtered.sort(key=lambda kv: (-kv[1], kv[0]))
    return [tag for tag, _ in filtered[:max_topics]]


def get_project_topics(
    projects_dir: Path,
    project_slug: str,
    session_metas: Iterable[Mapping[str, Any]],
) -> list[str]:
    """Return the topic list for a project using the precedence rules
    above: explicit profile first, session-tag fallback second."""
    profile = load_project_profile(projects_dir, project_slug)
    if profile and profile.get("topics"):
        return profile["topics"]
    return extract_session_topics(session_metas)


# ─── render ──────────────────────────────────────────────────────────────


def render_topic_chips(
    topics: list[str],
    max_visible: int = 6,
    classname: str = "project-topics",
) -> str:
    """Render a list of topics as a row of chip elements. Empty list
    returns an empty string. Overflow is collapsed into a `+N more`
    chip so the row stays one line on narrow cards."""
    if not topics:
        return ""
    visible = topics[:max_visible]
    hidden = len(topics) - len(visible)
    chip_html = "".join(
        f'<span class="topic-chip">{html.escape(t)}</span>'
        for t in visible
    )
    overflow = (
        f'<span class="topic-chip topic-chip-more">+{hidden} more</span>'
        if hidden > 0 else ""
    )
    return f'<div class="{html.escape(classname)}">{chip_html}{overflow}</div>'


def render_topic_chips_linked(
    topics: list[str],
    href_template: str = "../projects/index.html?topic={topic}",
    max_visible: int = 6,
    classname: str = "project-topics",
) -> str:
    """Same as `render_topic_chips` but wraps each chip in an `<a>` so
    clicking a topic can navigate to a filter view. The href is
    rendered via `href_template.format(topic=...)` with URL escaping."""
    if not topics:
        return ""
    import urllib.parse
    visible = topics[:max_visible]
    hidden = len(topics) - len(visible)
    chip_html = "".join(
        f'<a class="topic-chip" href="{html.escape(href_template.format(topic=urllib.parse.quote(t)))}">'
        f'{html.escape(t)}</a>'
        for t in visible
    )
    overflow = (
        f'<span class="topic-chip topic-chip-more">+{hidden} more</span>'
        if hidden > 0 else ""
    )
    return f'<div class="{html.escape(classname)}">{chip_html}{overflow}</div>'
