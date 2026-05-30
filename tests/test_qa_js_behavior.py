from __future__ import annotations

import re
from pathlib import Path


def _qa_js() -> str:
    return Path("llmwiki/web/static/components/qa.js").read_text(encoding="utf-8")


def test_reask_does_not_clear_current_thread():
    js = _qa_js()
    match = re.search(r"\n  reAsk\(question, model\) \{(?P<body>.*?)\n  \},", js, re.S)
    assert match, "QA.reAsk function not found"

    body = match.group("body")

    assert "this.threadId = null" not in body
    assert "this._updateThreadIndicator()" not in body
    assert "_sendAgent(question, model" in body
