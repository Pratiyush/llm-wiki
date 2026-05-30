from __future__ import annotations


def test_build_context_includes_web_source_url(tmp_path):
    from llmwiki.web.services.glm_client import build_context

    wiki_dir = tmp_path / "wiki"
    source_dir = wiki_dir / "sources" / "web"
    source_dir.mkdir(parents=True)
    (source_dir / "rule.md").write_text(
        """---
title: "Public Rule"
type: source
source_type: web
source_url: "https://example.gov.cn/rule.html"
canonical_url: "https://example.gov.cn/rule.html"
---

## Source

Government rule about procurement approval thresholds.
""",
        encoding="utf-8",
    )

    context = build_context("procurement approval thresholds", wiki_dir=wiki_dir)

    assert "Public Rule" in context
    assert "Web source URL: https://example.gov.cn/rule.html" in context
