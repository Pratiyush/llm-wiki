"""Shared helpers for lint rules.

Pre-#615 these lived inline at module scope in `llmwiki/lint/rules.py`.
After the per-rule split (#arch-m3) they sit here so every rule file can
import them without circular references back through `rules/__init__`.

Tests reach for these via either path:
- ``from llmwiki.lint.rules import _basename, _page_slug``  (pre-split)
- ``from llmwiki.lint.rules._helpers import _basename``      (direct)

Both are supported because `rules/__init__.py` re-exports the names.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any


def _basename(rel: str) -> str:
    """Return the last path component, normalising both ``/`` and ``\\``.

    #490: lint pages built on Windows have keys like
    ``wiki\\entities\\Foo.md`` (native ``Path.parts`` separators), so a
    ``rel.rsplit('/', 1)[-1]`` returns the *whole* string. This silently
    broke every exemption + slug-derivation site that assumed POSIX
    separators — every Windows install showed spurious lint errors
    against navigation files. Use this helper everywhere.
    """
    return rel.replace("\\", "/").rsplit("/", 1)[-1]


def _page_slug(rel: str) -> str:
    """Convert path like ``entities/Foo.md`` → ``Foo``."""
    return _basename(rel).removesuffix(".md")


def _resolve_index_href(href: str) -> str:
    """Normalise an index.md markdown link href to a repo-relative path.

    Strips ``#anchor`` and ``?query`` fragments, drops the leading
    ``./`` prefix, and collapses ``..`` segments using ``PurePosixPath``
    (POSIX-only — every wiki path is forward-slash). Returns ``""`` when
    the href is empty or escapes the wiki root.

    Closes #411 — the previous one-liner ``href.lstrip("./")`` only
    handled bare ``./`` and false-positive'd on ``../path``,
    ``path#anchor``, and ``path?query``.
    """
    href = href.split("#", 1)[0].split("?", 1)[0].strip()
    if not href:
        return ""
    parts: list[str] = []
    for seg in PurePosixPath(href).parts:
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                return ""
            parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


# Counters used by FrontmatterCountConsistency.
_TURN_USER_RE = re.compile(r"^### Turn \d+ — User\s*$", re.MULTILINE)
_TOOL_BULLET_RE = re.compile(
    r"^- `(Read|Write|Edit|Bash|Glob|Grep|Task|WebFetch|WebSearch|TodoWrite)`:",
    re.MULTILINE,
)

# Parsers used by ToolsConsistency.
_TOOLS_USED_RE = re.compile(r"\[([^\]]*)\]")
_TOOL_COUNTS_KEYS_RE = re.compile(r'"([A-Za-z_]+)"\s*:')


def _normalise_tools_used(value: Any) -> set[str]:
    """Coerce a frontmatter ``tools_used`` value into a set of tool names.

    Frontmatter parsers return either a Python ``list`` (when the value
    is parsed as ``[a, b]``) or a raw ``str`` (legacy paths or
    string-typed coercion). Older code did
    ``re.search(_TOOLS_USED_RE, value)`` directly — which raises
    ``TypeError`` on a list and silently aborted the whole lint rule
    (#410). This helper normalises both shapes plus the other types
    that have appeared in real frontmatter (number, bool, dict, None).
    """
    if value is None or value == "":
        return set()
    if isinstance(value, list):
        return {str(x).strip().strip('"\'') for x in value if str(x).strip()}
    if isinstance(value, str):
        m = _TOOLS_USED_RE.search(value)
        if not m:
            return set()
        return {
            t.strip().strip('"\'')
            for t in m.group(1).split(",")
            if t.strip()
        }
    return set()


def _normalise_tool_counts_keys(value: Any) -> set[str]:
    """Coerce a frontmatter ``tool_counts`` value into the set of keys.

    Symmetric to :func:`_normalise_tools_used`. Frontmatter often ships
    ``tool_counts`` as the raw inline JSON-looking string the converter
    wrote, but some pipelines (or future fixes) may return a real dict.
    """
    if value is None or value == "":
        return set()
    if isinstance(value, dict):
        return {str(k) for k in value.keys()}
    if isinstance(value, str):
        return set(_TOOL_COUNTS_KEYS_RE.findall(value))
    return set()
