"""Canonical frontmatter parser (#273).

Historically 8 copies of this function lived scattered across the
codebase with slightly different return shapes — dict vs
``(dict, body)`` tuple vs ``(str | None, body)``.  Consolidating in
one hit is risky (every caller makes specific assumptions about the
return shape), so this module ships the canonical implementation plus
thin wrappers that match the three existing signatures.  New call
sites should use :func:`parse_frontmatter` or
:func:`parse_frontmatter_dict`; legacy sites can migrate over time.

Stdlib-only.  No YAML dependency — we parse the minimal subset of
YAML we use in practice (scalars, inline lists, inline dicts, block
lists with `- ` bullets).
"""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple

# Accept LF, CRLF, or CR after each fence so Windows-authored (CRLF) and
# old-Mac (CR) files parse identically to LF input. The optional newline
# slots match the historical regex (`\n?(.*?)\n?---\n?`) so empty
# frontmatter (`---\n---\nbody`) still parses. BOM is handled separately
# in `_strip_bom()` before the regex runs. See #409, #423.
_FRONTMATTER_RE = re.compile(
    r"^---[ \t]*(?:\r\n|\r|\n)?(.*?)(?:\r\n|\r|\n)?---[ \t]*(?:\r\n|\r|\n)?(.*)$",
    re.DOTALL,
)


def _strip_bom(text: str) -> str:
    """Strip leading UTF-8 BOM if present (#423)."""
    if text and text[0] == "\ufeff":
        return text[1:]
    return text


def parse_frontmatter(text: str) -> Tuple[dict[str, Any], str]:
    """Return ``(meta, body)`` — the canonical shape.

    Empty or malformed input returns ``({}, text)`` so callers can
    treat every file uniformly. Handles UTF-8 BOM and CR/LF/CRLF
    line endings transparently.
    """
    text = _strip_bom(text)
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_text = m.group(1)
    body = m.group(2)
    meta: dict[str, Any] = {}
    for line in meta_text.splitlines():
        mm = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", line)
        if not mm:
            continue
        key, raw = mm.group(1), mm.group(2).strip()
        meta[key] = _parse_scalar(raw)
    return meta, body


def parse_frontmatter_dict(text: str) -> dict[str, Any]:
    """Return just the metadata dict — convenience for callers that
    don't need the body."""
    return parse_frontmatter(text)[0]


def parse_frontmatter_or_none(text: str) -> Tuple[Optional[str], str]:
    """Return ``(raw_frontmatter_text | None, body)`` — legacy shape
    used by ``llmwiki/tags.py`` which does its own line-level parsing
    inside the frontmatter block."""
    text = _strip_bom(text)
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def _parse_scalar(raw: str) -> Any:
    """Parse a single YAML scalar value (best-effort, no external deps).

    Handles: inline lists ``[a, b, c]``, quoted strings, bools, ints.
    Everything else comes back as the stripped string.
    """
    s = raw.strip()
    if not s:
        return ""
    # Quoted string
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    # Inline list: [a, b, c]
    if s.startswith("[") and s.endswith("]"):
        body = s[1:-1].strip()
        if not body:
            return []
        return [_parse_scalar(x) for x in body.split(",")]
    # Bool
    low = s.lower()
    if low in {"true", "yes"}:
        return True
    if low in {"false", "no"}:
        return False
    # Int
    try:
        return int(s)
    except ValueError:
        pass
    # Float
    try:
        return float(s)
    except ValueError:
        pass
    return s
