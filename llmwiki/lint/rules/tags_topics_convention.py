"""tags_topics_convention — projects use `topics:`, everything else uses `tags:`."""

from __future__ import annotations

from llmwiki.lint import LintRule, register


@register
class TagsTopicsConvention(LintRule):
    """Projects use `topics:`, everything else uses `tags:` (G-16 · #302).

    `wiki/projects/<slug>.md` carries curated stack labels
    (React, ML, Java) under ``topics:``.
    `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/syntheses/`
    carry freeform per-page labels under ``tags:``. Mixing the two
    breaks filtering in the site UI and makes the graph viewer's chip
    rendering inconsistent — this rule flags the mismatch.
    """

    name = "tags_topics_convention"
    severity = "warning"

    _PROJECT_PREFIX = "projects/"
    _TAG_PREFIXES = (
        "sources/", "entities/", "concepts/", "syntheses/",
    )

    def run(self, pages, *, llm_callback=None):
        issues = []
        for rel, page in pages.items():
            rel_posix = rel.replace("\\", "/")
            meta = page["meta"]
            has_tags = "tags" in meta
            has_topics = "topics" in meta
            if rel_posix.startswith(self._PROJECT_PREFIX):
                if has_tags and not has_topics:
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel,
                        "message": (
                            "project pages should use `topics:` not `tags:` — "
                            "run `llmwiki tag rename <value> <value>` to fix "
                            "or set topics: directly"
                        ),
                    })
            elif any(rel_posix.startswith(p) for p in self._TAG_PREFIXES):
                if has_topics and not has_tags:
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel,
                        "message": (
                            f"{rel_posix.split('/')[0]} pages should use `tags:` "
                            "not `topics:`"
                        ),
                    })
        return issues
