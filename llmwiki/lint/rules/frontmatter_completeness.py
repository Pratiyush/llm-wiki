"""frontmatter_completeness — required frontmatter fields must be present."""

from __future__ import annotations

from llmwiki.lint import LintRule, register
from llmwiki.lint.rules._helpers import _basename


@register
class FrontmatterCompleteness(LintRule):
    """Required frontmatter fields must be present."""

    name = "frontmatter_completeness"
    severity = "error"
    auto_fixable = False

    REQUIRED = ["title", "type"]

    # System-level nav files and _context.md stubs are exempt from the
    # strict title/type requirement. Index/log/overview are auto-generated
    # or human-curated hubs and don't fit the source/entity/concept schema.
    # #arch-l7: canonical list lives in llmwiki/_system_pages.py so
    # graph.py + lint don't drift independently. Use the .md-filename
    # form because lint walks page paths read off disk.
    from llmwiki._system_pages import SYSTEM_PAGE_FILES as EXEMPT_FILES

    def run(self, pages, *, llm_callback=None):
        issues = []
        for rel, page in pages.items():
            # Skip system nav files and _context.md stubs.
            # #490: use the separator-agnostic basename helper so
            # exemptions still fire on Windows-built page paths
            # (`wiki\\index.md` etc.).
            basename = _basename(rel)
            if basename in self.EXEMPT_FILES or basename == "_context.md":
                continue
            meta = page["meta"]
            missing = [f for f in self.REQUIRED if f not in meta]
            if missing:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": rel,
                    "message": f"missing required fields: {', '.join(missing)}",
                })
        return issues
