# Conversation Follow-ups Design

## Goal

Improve same-thread question answering so follow-up questions can rely on prior questions and answers. A user should be able to ask a focused first question, then ask a broader or narrower follow-up such as "for the previous question, search all company management policies" and have the system understand what "previous question" refers to.

This is phase 1 only. Web page ingestion and URL citation support are intentionally deferred to a separate phase.

## Current Behavior

The web app already stores conversations with `Conversation`, `ChatHistory`, and `thread_id`. Agent mode can inject recent thread history through `_build_thread_history()`, but the implementation is shallow:

- Only agent mode receives thread history; `ask` and `stream` do not.
- History is plain text with a fixed answer truncation.
- "Re-ask with different model" clears `threadId`, so a repeated answer loses the current conversation.
- The prompt does not explicitly resolve references such as "the previous question", "this issue", or "continue".

## Proposed Architecture

Add a focused backend service:

```text
llmwiki/web/services/conversation_context.py
```

The service builds a compact, deterministic context block from the current user's current notebook thread. It does not add new database tables or persistent summaries.

`llmwiki/web/routes/query.py` will call this service for all Q&A paths:

- `POST /api/query/agent`
- `POST /api/query/stream`
- `POST /api/query/ask`

The LLM client functions will accept an optional `conversation_context` argument and include it in the system prompt before the current user question.

## Context Rules

The context builder reads only rows matching:

- current authenticated user
- current notebook
- current `thread_id`

It returns an empty string if no valid thread is available.

Default limits:

- Maximum 6 prior Q&A rounds.
- Recent 2 rounds keep the full question and a larger answer excerpt.
- Older 4 rounds keep the full question, a shorter answer excerpt, and extracted source links.
- Source extraction recognizes existing `[[Page Name]]` citations in answers.

If the current question contains referential language, the builder adds a "current thread topic" section that tells the model the current question may depend on prior turns. Trigger phrases include these Chinese expressions, represented here as Unicode escapes to keep this spec ASCII-safe:

- `\u4e0a\u4e00\u4e2a\u95ee\u9898` ("previous question")
- `\u521a\u624d` ("just now")
- `\u7ee7\u7eed` ("continue")
- `\u8fd9\u4e2a\u95ee\u9898` ("this question")
- `\u8be5\u95ee\u9898` ("that question")
- `\u524d\u9762` ("earlier")
- `\u4e0a\u4e00\u95ee` ("previous ask")
- `\u8865\u5145` ("supplement")

The context block should be concise and clearly labeled, for example:

```text
## Current conversation context
The following content comes from prior Q&A in the same thread. Use it only to resolve references in the current question.

### Current thread topic
The current question may refer to recent turns. Interpret it with the full meaning of the latest user question.

### Recent Q&A
User: ...
Assistant: ...

### Older Q&A summary
User: ...
Assistant summary: ...
Cited sources: [[...]], [[...]]
```

## Prompt Integration

`glm_client.ask()`, `ask_stream()`, and `ask_agent()` will all support optional conversation context.

Ordering inside the prompt:

1. Role and answer-format instructions.
2. Conversation context.
3. Retrieved wiki context or agent preload context.
4. Current user question.

Conversation context must not replace wiki retrieval. It only clarifies what the user means; factual answers must still be grounded in wiki pages.

## UI Behavior

Follow-up suggestions already call `_sendFollowup()`, which preserves `threadId`; that behavior remains.

`QA.reAsk(question, model)` must stop resetting `threadId`. Re-asking should remain inside the current thread so model comparison or a more complete second answer can see the same conversation context.

The explicit "new conversation" button remains the way to intentionally clear context.

## Error Handling

Conversation context is best-effort:

- If history lookup fails, the route continues with no conversation context.
- If a supplied `thread_id` is inaccessible or belongs to another notebook/user, no history is injected.
- Long answers are truncated deterministically to preserve room for retrieved policy text.
- Context building never calls an LLM, so it cannot add network latency or fail due to model errors.

## Security and Privacy

Thread history must never cross user or notebook boundaries. The context builder will accept the resolved `User` and `Notebook` identities or equivalent IDs, then query by all relevant IDs.

The frontend must not send raw history back to the server. Server-side history remains the source of truth.

## Tests

Add focused tests for:

- Recent 2 rounds include fuller answer excerpts.
- Older rounds include shorter summaries and extracted `[[source]]` citations.
- Referential questions add the current-thread-topic section.
- Non-referential questions omit the extra topic section.
- Invalid or missing thread returns empty context.
- `agent`, `stream`, and `ask` routes pass conversation context to the LLM client.
- `QA.reAsk()` no longer clears `threadId`.

## Non-Goals

- No web page ingestion in this phase.
- No persistent conversation summary table.
- No vector store or semantic memory.
- No cross-thread memory.
- No change to notebook permission rules.

## Acceptance Criteria

1. A follow-up question in the same thread can reference "the previous question" and the prompt receives enough context to resolve it.
2. Re-asking a question with another model stays in the same thread.
3. All Q&A modes have consistent access to conversation context.
4. Existing authorization boundaries remain intact.
5. Unit tests cover the context builder and route integration.
