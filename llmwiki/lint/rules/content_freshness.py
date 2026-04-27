"""content_freshness — pages older than 90 days should be reviewed."""

from __future__ import annotations

from datetime import datetime, timezone

from llmwiki.lint import LintRule, register


@register
class ContentFreshness(LintRule):
    """Pages older than 90 days should be reviewed."""

    name = "content_freshness"
    severity = "warning"

    STALE_DAYS = 90

    def run(self, pages, *, llm_callback=None):
        issues = []
        now = datetime.now(timezone.utc)
        for rel, page in pages.items():
            meta = page["meta"]
            date_str = meta.get("last_verified") or meta.get("last_updated")
            if not date_str:
                continue
            try:
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            age_days = (now - dt).days
            if age_days > self.STALE_DAYS:
                issues.append({
                    "rule": self.name,
                    "severity": "warning",
                    "page": rel,
                    "message": f"last updated {age_days} days ago (> {self.STALE_DAYS} day threshold)",
                })
        return issues
