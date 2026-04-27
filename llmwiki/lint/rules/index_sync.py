"""index_sync — wiki/index.md must list every page, and listed pages must exist."""

from __future__ import annotations

import re

from llmwiki.lint import LintRule, register
from llmwiki.lint.rules._helpers import _basename, _page_slug, _resolve_index_href


@register
class IndexSync(LintRule):
    """wiki/index.md must list every page, and listed pages must exist."""

    name = "index_sync"
    severity = "error"
    auto_fixable = True

    def run(self, pages, *, llm_callback=None):
        index = pages.get("index.md")
        if not index:
            return []

        issues = []
        listed_slugs: set[str] = set()

        # #411: index.md lives at the wiki root, so the resolver works
        # against PurePosixPath("") as the base. We collapse `..`,
        # drop `#anchor` and `?query`, and look the resulting
        # repo-relative path up in `pages`. The old `href.lstrip("./")`
        # only handled bare `./` and false-positive'd on every other
        # form (`../`, `#anchor`, `?query`).
        # Parse markdown links in index.md (simple regex)
        link_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for match in link_re.finditer(index["body"]):
            href = match.group(2)
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = _resolve_index_href(href)
            if not resolved:
                continue
            if resolved in pages:
                listed_slugs.add(_basename(resolved).removesuffix(".md"))
            else:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": "index.md",
                    "message": f"dead index link → {href}",
                })

        # Check that every content page is listed (skip nav files and _context.md)
        # #py-m5 (#591): pull from the canonical SYSTEM_PAGE_FILES list
        # rather than redeclaring it inline (third copy of the same set
        # in this file before the consolidation).
        from llmwiki._system_pages import SYSTEM_PAGE_FILES as nav_pages
        for rel in pages:
            if rel in nav_pages or rel.endswith("_context.md"):
                continue
            slug = _page_slug(rel)
            if slug not in listed_slugs:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": "index.md",
                    "message": f"page {rel!r} not listed in index.md",
                })
        return issues
