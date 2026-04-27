"""All registered lint rules (#615 split — was a single 968-LOC rules.py).

Basic rules (8, no LLM):
  1. frontmatter_completeness  — required fields present
  2. frontmatter_validity       — enum values + types valid
  3. link_integrity             — [[wikilinks]] resolve
  4. orphan_detection           — pages with zero inbound links
  5. content_freshness          — last_updated > 90 days → warning
  6. entity_consistency         — entities in body match frontmatter
  7. duplicate_detection        — same-project + title + body similarity
  8. index_sync                 — pages in index.md ↔ pages on disk

LLM-powered rules (3):
  9. contradiction_detection
  10. claim_verification
  11. summary_accuracy

Post-v1.0 rules:
  12. stale_candidates            (v1.1 · #51)
  13. tags_topics_convention      (G-16 · #302)
  14. stale_reference_detection   (G-17 · #303)
  15. frontmatter_count_consistency  (v1.2 · issues.md #2)
  16. tools_consistency              (v1.2 · issues.md #4)

Import order matters — every per-rule module's top-level ``@register``
decorator runs at import time and inserts its rule into the
``llmwiki.lint.REGISTRY`` dict in the order seen here. The ordering
matches the pre-split file so any test or downstream consumer that
relied on enumeration order continues to see the same sequence.

The live rule count lives in ``llmwiki.lint.REGISTRY`` — prefer
``len(REGISTRY)`` over hard-coded numbers in docs + help strings.
"""

from __future__ import annotations

# Helpers exported for back-compat with pre-split imports
# (e.g. ``from llmwiki.lint.rules import _basename, _page_slug``).
# tests/test_lint_windows_paths.py reaches for them this way.
from llmwiki.lint.rules._helpers import (  # noqa: F401
    _basename,
    _normalise_tool_counts_keys,
    _normalise_tools_used,
    _page_slug,
    _resolve_index_href,
    _TOOL_BULLET_RE,
    _TOOL_COUNTS_KEYS_RE,
    _TOOLS_USED_RE,
    _TURN_USER_RE,
)

# Rule classes — order matches the pre-split file so REGISTRY enumeration
# is stable. Each module's top-level @register call runs at import time.
from llmwiki.lint.rules.frontmatter_completeness import FrontmatterCompleteness  # noqa: F401
from llmwiki.lint.rules.frontmatter_validity import FrontmatterValidity  # noqa: F401
from llmwiki.lint.rules.link_integrity import LinkIntegrity  # noqa: F401
from llmwiki.lint.rules.orphan_detection import OrphanDetection  # noqa: F401
from llmwiki.lint.rules.content_freshness import ContentFreshness  # noqa: F401
from llmwiki.lint.rules.entity_consistency import EntityConsistency  # noqa: F401
from llmwiki.lint.rules.duplicate_detection import DuplicateDetection  # noqa: F401
from llmwiki.lint.rules.index_sync import IndexSync  # noqa: F401
from llmwiki.lint.rules.contradiction_detection import ContradictionDetection  # noqa: F401
from llmwiki.lint.rules.claim_verification import ClaimVerification  # noqa: F401
from llmwiki.lint.rules.stale_candidates import StaleCandidates  # noqa: F401
from llmwiki.lint.rules.summary_accuracy import SummaryAccuracy  # noqa: F401
from llmwiki.lint.rules.tags_topics_convention import TagsTopicsConvention  # noqa: F401
from llmwiki.lint.rules.stale_reference_detection import StaleReferenceDetection  # noqa: F401
from llmwiki.lint.rules.frontmatter_count_consistency import FrontmatterCountConsistency  # noqa: F401
from llmwiki.lint.rules.tools_consistency import ToolsConsistency  # noqa: F401
