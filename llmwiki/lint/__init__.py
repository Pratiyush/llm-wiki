"""Lint rule registry (v1.0 · #155).

Originally the 11 rules from the LLM Book design spec
(08-quality-maintenance.md); has since grown past that.  The live
count is ``len(REGISTRY)`` — see ``llmwiki/lint/rules.py`` for the
canonical list.  Each rule is a subclass of :class:`LintRule`
registered via the ``@register`` decorator.

Usage::

    from llmwiki.lint import run_all, load_pages

    pages = load_pages()  # reads wiki/*.md into dicts
    issues = run_all(pages)
    for issue in issues:
        print(f"{issue['severity']} [{issue['rule']}] {issue['message']}")

Rule severity levels: ``error``, ``warning``, ``info``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Optional

from llmwiki import REPO_ROOT

WIKI_DIR = REPO_ROOT / "wiki"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


class LintRule:
    """Base class for lint rules."""

    name: str = "base"
    description: str = ""
    severity: str = "warning"
    auto_fixable: bool = False
    requires_llm: bool = False

    def run(
        self,
        pages: dict[str, dict[str, Any]],
        *,
        llm_callback: Optional[Callable[[str], str]] = None,
    ) -> list[dict[str, Any]]:
        """Run the rule against the given pages. Return a list of issues.

        Each issue dict has: ``rule`` (name), ``severity``, ``page`` (path),
        ``message``, optional ``fix`` (auto-fix suggestion).
        """
        raise NotImplementedError


REGISTRY: dict[str, type[LintRule]] = {}


def register(cls: type[LintRule]) -> type[LintRule]:
    """Decorator to register a lint rule."""
    REGISTRY[cls.name] = cls
    return cls


# ─── Page loading ──────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse YAML-like frontmatter from markdown text."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"')
    return out


def load_pages(wiki_dir: Optional[Path] = None) -> dict[str, dict[str, Any]]:
    """Load all wiki pages. Returns dict of relative_path → page dict.

    Each page dict has: ``path``, ``text``, ``meta`` (frontmatter), ``body``.
    """
    root = wiki_dir or WIKI_DIR
    if not root.is_dir():
        return {}
    pages: dict[str, dict[str, Any]] = {}
    for p in sorted(root.rglob("*.md")):
        # Skip README and archive
        if p.name == "README.md":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = parse_frontmatter(text)
        body = FRONTMATTER_RE.sub("", text, count=1)
        rel = str(p.relative_to(root))
        pages[rel] = {
            "path": p,
            "rel": rel,
            "text": text,
            "meta": meta,
            "body": body,
        }
    return pages


# ─── Runner ────────────────────────────────────────────────────────────

def run_all(
    pages: dict[str, dict[str, Any]],
    *,
    include_llm: bool = False,
    llm_callback: Optional[Callable[[str], str]] = None,
    selected: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Run all registered lint rules. Returns a flat list of issues.

    Parameters
    ----------
    pages : dict
        Output of :func:`load_pages`.
    include_llm : bool
        If True, also run LLM-powered rules (requires_llm=True).
    llm_callback : callable, optional
        Function that takes a prompt string and returns a response.
        Required when include_llm=True.
    selected : list[str], optional
        Run only these rules by name. Default: all.
    """
    # Import all rule modules so they register themselves
    from llmwiki.lint import rules  # noqa: F401

    issues: list[dict[str, Any]] = []
    for name, rule_cls in REGISTRY.items():
        if selected and name not in selected:
            continue
        if rule_cls.requires_llm and not include_llm:
            continue
        rule = rule_cls()
        try:
            issues.extend(rule.run(pages, llm_callback=llm_callback))
        except Exception as e:
            issues.append({
                "rule": name,
                "severity": "error",
                "page": "",
                "message": f"rule raised exception: {e}",
            })
    return issues


def summarize(issues: list[dict[str, Any]]) -> dict[str, int]:
    """Return {severity: count} summary."""
    summary: dict[str, int] = {}
    for i in issues:
        sev = i.get("severity", "info")
        summary[sev] = summary.get(sev, 0) + 1
    return summary
