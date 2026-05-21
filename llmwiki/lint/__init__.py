"""Lint rule registry (v1.0 · #155).

Implements the 11 lint rules from the LLM Book design spec
(08-quality-maintenance.md). Each rule is a subclass of :class:`LintRule`
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

import json
import re
from pathlib import Path
from typing import Any, Callable, Optional

from llmwiki import REPO_ROOT
from llmwiki.text_utils import strip_bom

WIKI_DIR = REPO_ROOT / "wiki"
LINT_STATE_FILE = REPO_ROOT / ".llmwiki-lint-state.json"
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
    text = strip_bom(text)
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
        rel = str(p.relative_to(root)).replace("\\", "/")
        pages[rel] = {
            "path": p,
            "rel": rel,
            "text": text,
            "meta": meta,
            "body": body,
        }
    return pages


def load_incremental_pages(
    wiki_dir: Optional[Path] = None,
    *,
    force_full: bool = False,
) -> tuple[dict[str, dict[str, Any]], bool]:
    """Load wiki pages, returning only changed/new ones since last scan.

    Returns (pages, is_full_scan). When ``is_full_scan`` is False, unchanged
    pages are excluded so rules only re-check files that were modified. Rule
    implementations should still scan the full set for cross-page checks
    (orphans, link integrity) — the caller decides which rules to run.
    """
    root = wiki_dir or WIKI_DIR
    all_pages = load_pages(root)
    if force_full or not all_pages:
        return all_pages, True

    # Build current mtime snapshot
    current_mtimes: dict[str, float] = {}
    for rel, info in all_pages.items():
        current_mtimes[rel] = info["path"].stat().st_mtime

    # Load previous state
    prev_mtimes: dict[str, float] = {}
    if LINT_STATE_FILE.is_file():
        try:
            prev_mtimes = json.loads(LINT_STATE_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    # Find changed/new pages
    changed: dict[str, dict[str, Any]] = {}
    for rel, info in all_pages.items():
        prev_mtime = prev_mtimes.get(rel)
        if prev_mtime is None or current_mtimes[rel] != prev_mtime:
            changed[rel] = info

    # If many pages changed (e.g. bulk ingest), fall back to full scan
    if len(changed) > len(all_pages) * 0.5:
        return all_pages, True

    # Persist new mtimes
    LINT_STATE_FILE.write_text(json.dumps(current_mtimes, indent=2), encoding="utf-8")

    if not changed:
        return {}, False

    return changed, False


# ─── Runner ────────────────────────────────────────────────────────────

def run_all(
    pages: dict[str, dict[str, Any]],
    *,
    include_llm: bool = False,
    llm_callback: Optional[Callable[[str], str]] = None,
    selected: Optional[list[str]] = None,
    incremental: bool = False,
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
    selected : list[str], optional
        Run only these rules by name. Default: all.
    incremental : bool
        If True, ``pages`` contains only changed pages. Cross-page
        rules (link integrity, orphans, index sync) are still run
        against the full wiki; per-page rules skip unchanged files.
    """
    # Import all rule modules so they register themselves
    from llmwiki.lint import rules  # noqa: F401

    # When incremental, always run cross-page rules against full set
    cross_page_rules = {"LinkIntegrity", "OrphanDetection", "IndexSync"}

    issues: list[dict[str, Any]] = []
    for name, rule_cls in REGISTRY.items():
        if selected and name not in selected:
            continue
        if rule_cls.requires_llm and not include_llm:
            continue
        rule = rule_cls()
        try:
            if incremental and name in cross_page_rules and pages:
                # Cross-page rules need the full wiki to be correct
                full_pages = load_pages()
                issues.extend(rule.run(full_pages, llm_callback=llm_callback))
            else:
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
