from __future__ import annotations

import pytest


def test_validate_public_url_blocks_unsafe_targets():
    from llmwiki.web.services.web_ingester import validate_public_url

    for url in [
        "file:///etc/passwd",
        "ftp://example.com/a",
        "http://localhost/a",
        "http://127.0.0.1/a",
        "http://10.0.0.1/a",
        "http://172.16.0.1/a",
        "http://192.168.1.1/a",
        "http://169.254.169.254/latest/meta-data",
    ]:
        with pytest.raises(ValueError):
            validate_public_url(url)


def test_process_manual_web_import_preserves_url_metadata(monkeypatch, tmp_path):
    from llmwiki.web.services import web_ingester

    def fake_getaddrinfo(host, port, type=0):
        return [(None, None, None, "", ("93.184.216.34", port))]

    monkeypatch.setattr(web_ingester.socket, "getaddrinfo", fake_getaddrinfo)
    wiki_dir = tmp_path / "notebooks" / "ai" / "wiki"
    raw_dir = tmp_path / "notebooks" / "ai" / "raw" / "web"
    body = "Article paragraph one.\n\nArticle paragraph two with enough content for import."

    result = web_ingester.process_web_import(
        "https://example.gov.cn/rule.html",
        title="Public Rule",
        content=body,
        mode="manual",
        raw_dir=raw_dir,
        wiki_dir=wiki_dir,
    )

    assert result["status"] == "ok"
    assert result["source_type"] == "web"
    assert result["url"] == "https://example.gov.cn/rule.html"
    assert result["capture_method"] == "manual"
    source_path = wiki_dir / result["wiki_path"]
    text = source_path.read_text(encoding="utf-8")
    assert "source_type: web" in text
    assert 'source_url: "https://example.gov.cn/rule.html"' in text
    assert "capture_method: manual" in text
    assert "- URL: https://example.gov.cn/rule.html" in text
    assert body in text
