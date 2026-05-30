from __future__ import annotations

from datetime import datetime, timedelta


def test_extract_cited_sources_dedupes_in_order():
    from llmwiki.web.services.conversation_context import extract_cited_sources

    answer = "See [[PPP Contract]] and [[Articles]]. Also [[PPP Contract]]."

    assert extract_cited_sources(answer) == ["PPP Contract", "Articles"]


def test_referential_question_detection_uses_chinese_triggers():
    from llmwiki.web.services.conversation_context import is_referential_question

    assert is_referential_question("\u5bf9\u4e8e\u4e0a\u4e00\u4e2a\u95ee\u9898\uff0c\u8bf7\u6269\u5927\u68c0\u7d22\u8303\u56f4")
    assert is_referential_question("\u521a\u624d\u7684\u7b54\u6848\u4e0d\u5168\u9762\uff0c\u7ee7\u7eed\u5206\u6790")
    assert not is_referential_question("\u8bf7\u8bf4\u660ePPP\u5408\u540c\u5ba1\u6279\u6d41\u7a0b")


def test_format_history_keeps_recent_rounds_fuller_and_older_sources():
    from llmwiki.web.services.conversation_context import format_history_records

    base = datetime(2026, 5, 30, 9, 0, 0)
    records = []
    for i in range(1, 7):
        records.append(
            {
                "question": f"question {i}",
                "answer": f"answer {i} " + ("x" * 600) + f" [[Source{i}]]",
                "created_at": base + timedelta(minutes=i),
            }
        )

    context = format_history_records(records, "\u5bf9\u4e8e\u4e0a\u4e00\u4e2a\u95ee\u9898\uff0c\u7ee7\u7eed")

    assert "## Current conversation context" in context
    assert "### Current thread topic" in context
    assert "### Recent Q&A" in context
    assert "User: question 5" in context
    assert "User: question 6" in context
    assert "### Older Q&A summary" in context
    assert "User: question 1" in context
    assert "Cited sources: [[Source1]]" in context
    assert context.index("### Recent Q&A") < context.index("### Older Q&A summary")
    assert context.index("User: question 5") < context.index("User: question 6")


def test_format_history_omits_topic_for_standalone_question():
    from llmwiki.web.services.conversation_context import format_history_records

    context = format_history_records(
        [{"question": "old q", "answer": "old a [[Doc]]"}],
        "\u8bf7\u8bf4\u660e\u5408\u540c\u5ba1\u6279",
    )

    assert "## Current conversation context" in context
    assert "### Current thread topic" not in context


def test_build_messages_puts_conversation_before_wiki_context(monkeypatch):
    import llmwiki.web.services.glm_client as glm

    monkeypatch.setattr(glm, "build_context", lambda question, wiki_dir=None: "WIKI CONTEXT")

    messages = glm._build_ask_messages(
        "current question",
        conversation_context="THREAD CONTEXT",
        wiki_dir=None,
    )

    system = messages[0]["content"]
    assert system.index("THREAD CONTEXT") < system.index("WIKI CONTEXT")
    assert messages[1] == {"role": "user", "content": "current question"}


def test_build_agent_system_content_includes_conversation_before_preload(monkeypatch):
    import llmwiki.web.services.glm_client as glm

    monkeypatch.setattr(glm, "_preload_context", lambda question, wiki_dir=None: "PRELOADED WIKI")

    content = glm._build_agent_system_content(
        "current question",
        conversation_context="THREAD CONTEXT",
        wiki_dir=None,
    )

    assert content.index("THREAD CONTEXT") < content.index("PRELOADED WIKI")
