"""Jira REST API adapter (v1.0 · #147).

Fetches tickets from Jira via REST API and converts them to
frontmatter-tagged markdown for ingestion into the wiki.

Requires the optional ``jira`` package: ``pip install jira``
and optionally ``jira2markdown`` for rich description formatting.

Configuration (in ``sessions_config.json``):

  - ``jira.enabled``: bool (default: false — opt-in)
  - ``jira.server``: str — Jira server URL
  - ``jira.email``: str — Jira account email
  - ``jira.api_token``: str — Jira API token (NOT password)
  - ``jira.jql``: str — JQL filter for tickets (default: "assignee = currentUser()")
  - ``jira.max_results``: int — max tickets per fetch (default: 50)

Disabled by default. The adapter gracefully degrades when ``jira``
is not installed — ``is_available()`` returns False.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


def _jira_available() -> bool:
    """Check if the jira library is installed."""
    try:
        import jira  # noqa: F401
        return True
    except ImportError:
        return False


def _j2m_available() -> bool:
    """Check if jira2markdown is installed."""
    try:
        import jira2markdown  # noqa: F401
        return True
    except ImportError:
        return False


@register("jira")
class JiraAdapter(BaseAdapter):
    """Jira REST API adapter — fetches tickets and converts to markdown."""

    #: #326: Jira tickets are organisational content, not AI sessions.
    is_ai_session = False

    session_store_path: Path | list[Path] = Path("/dev/null")

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        jc = (config or {}).get("jira", {})
        self._enabled = jc.get("enabled", False)
        self._server = jc.get("server", "")
        self._email = jc.get("email", "")
        self._api_token = jc.get("api_token", "")
        self._jql = jc.get("jql", "assignee = currentUser()")
        self._max_results = jc.get("max_results", 50)

    @classmethod
    def is_available(cls) -> bool:
        # Disabled by default — user must opt in and have jira installed
        return False

    def is_available_with_config(self) -> bool:
        """Check availability using instance config."""
        return (
            self._enabled
            and _jira_available()
            and bool(self._server)
            and bool(self._email)
            and bool(self._api_token)
        )

    def discover_sessions(self) -> list[Path]:
        """Jira doesn't use file discovery — returns empty list.
        Use ``fetch_tickets()`` instead.
        """
        return []

    def fetch_tickets(self) -> list[dict[str, Any]]:
        """Fetch tickets from Jira REST API.

        Returns a list of dicts with: key, summary, status, assignee,
        reporter, created, updated, description, labels, priority,
        issue_type, project.

        Raises ImportError if ``jira`` is not installed.
        """
        if not _jira_available():
            raise ImportError(
                "The 'jira' package is required for the Jira adapter. "
                "Install it with: pip install jira"
            )
        from jira import JIRA

        client = JIRA(
            server=self._server,
            basic_auth=(self._email, self._api_token),
        )
        issues = client.search_issues(
            self._jql,
            maxResults=self._max_results,
            fields="summary,status,assignee,reporter,created,updated,"
                   "description,labels,priority,issuetype,project",
        )
        tickets: list[dict[str, Any]] = []
        for issue in issues:
            f = issue.fields
            tickets.append({
                "key": issue.key,
                "summary": f.summary or "",
                "status": str(f.status) if f.status else "",
                "assignee": str(f.assignee) if f.assignee else "",
                "reporter": str(f.reporter) if f.reporter else "",
                "created": str(f.created) if f.created else "",
                "updated": str(f.updated) if f.updated else "",
                "description": f.description or "",
                "labels": list(f.labels) if f.labels else [],
                "priority": str(f.priority) if f.priority else "",
                "issue_type": str(f.issuetype) if f.issuetype else "",
                "project": str(f.project) if f.project else "",
            })
        return tickets


def convert_jira_description(description: str) -> str:
    """Convert Jira wiki markup to markdown.

    Uses jira2markdown if available, otherwise does basic cleanup.
    """
    if not description:
        return ""
    if _j2m_available():
        from jira2markdown import convert
        return convert(description)
    # Basic fallback: strip common Jira markup
    text = description
    text = re.sub(r"\{code(?::[^}]*)?\}", "```", text)
    text = re.sub(r"\{noformat\}", "```", text)
    text = re.sub(r"\{color:[^}]*\}(.*?)\{color\}", r"\1", text)
    text = re.sub(r"\[([^|]+)\|([^\]]+)\]", r"[\1](\2)", text)  # [text|url]
    text = text.replace("h1. ", "# ")
    text = text.replace("h2. ", "## ")
    text = text.replace("h3. ", "### ")
    text = text.replace("*", "**")  # bold approximation
    return text


def render_ticket_markdown(ticket: dict[str, Any]) -> str:
    """Render a Jira ticket as frontmatter-tagged markdown."""
    key = ticket["key"]
    summary = ticket["summary"]
    description = convert_jira_description(ticket.get("description", ""))

    fm = [
        "---",
        f'title: "{key}: {summary}"',
        "type: source",
        f"tags: [jira, {ticket.get('issue_type', 'task').lower()}]",
        f"date: {ticket.get('created', '')[:10]}",
        f"source_file: jira/{key}",
        f"project: {ticket.get('project', 'jira')}",
        f"jira_key: {key}",
        f"jira_status: {ticket.get('status', '')}",
        f"jira_priority: {ticket.get('priority', '')}",
        f"jira_assignee: {ticket.get('assignee', '')}",
        "---",
        "",
        f"# {key}: {summary}",
        "",
        f"**Status:** {ticket.get('status', '')} · "
        f"**Priority:** {ticket.get('priority', '')} · "
        f"**Assignee:** {ticket.get('assignee', '')}",
        "",
    ]

    if ticket.get("labels"):
        fm.append(f"**Labels:** {', '.join(ticket['labels'])}")
        fm.append("")

    if description:
        fm.append("## Description")
        fm.append("")
        fm.append(description)
        fm.append("")

    fm.append("## Connections")
    fm.append("")
    fm.append(f"- Source: Jira {ticket.get('project', '')}")
    fm.append("")

    return "\n".join(fm)
