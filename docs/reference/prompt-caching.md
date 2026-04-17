# Prompt caching + batch API

> Status: scaffold (v1.1.0 · #50). The plumbing — cache-block
> construction, token estimator, batch-state store — lives in
> `llmwiki/cache.py`. The actual Anthropic backend that consumes it
> lands in v1.2 behind a separate PR.

## Why cache prompts?

Every `/wiki-sync` and `/wiki-ingest` bundles the same stable prefix
with every source file it asks the model to summarize:

- The `CLAUDE.md` schema (~3 k tokens)
- The current `wiki/index.md` (grows with the wiki)
- The current `wiki/overview.md`

On a 500-page wiki that prefix is ≈ 30 k tokens **per request**. Marking
the prefix with `cache_control: { type: "ephemeral" }` tells Anthropic
to cache it server-side; subsequent calls pay the `cached_input` rate
(10 % of the fresh `input` rate) instead of the full input rate.

sage-wiki reports **50–90 % savings** on bulk ingest with this pattern.

## Build a cached prompt

```python
from llmwiki.cache import CachedPrompt, build_messages

prompt = CachedPrompt(
    stable_prefix=claude_md_schema + current_index + current_overview,
    dynamic_suffix=session_body,
)

messages = build_messages(prompt)
# [
#   {
#     "role": "user",
#     "content": [
#       {"type": "text", "text": "...schema + index + overview...",
#        "cache_control": {"type": "ephemeral"}},
#       {"type": "text", "text": "...session body..."},
#     ],
#   },
# ]
```

The cache header lives on the *last* block you want cached, so
`make_cached_block()` always puts the prefix before the dynamic suffix.

## Estimate cost before you spend

```
$ llmwiki synthesize --estimate
627 new sessions, prefix 3,944 tok
Model: claude-sonnet-4-6 (first write)
  Prefix:   3,944 tok  $0.0148
  Fresh:    1,274 tok  $0.0038
  Output:   1,000 tok  $0.0150
  Total:                $0.0336
  + 626 subsequent sessions (cache hit):  $17.9484

Batch total: $17.9820 (model claude-sonnet-4-6)
```

`--estimate` never calls the API — it uses the `char / 4` heuristic
from `estimate_tokens()` and the rate table in `MODEL_PRICING`. Treat
it as ± 20 %; the real numbers come back in `usage` on each response.

If the prefix is below Anthropic's minimum cache size (1 024 tokens),
`--estimate` prints a warning:

```
warning: prefix is 400 tok (< 1024 min) — Anthropic will not cache it;
savings estimate is best-case only.
```

## Batch submission

Large backfills can go through Anthropic's `message_batches` endpoint
(up to 50 % cheaper and no per-request rate limit). The scaffolding
tracks in-flight batches on disk:

```python
from pathlib import Path
from llmwiki.cache import (
    BatchJob,
    BatchState,
    add_pending,
    load_batch_state,
    mark_completed,
    save_batch_state,
)

repo = Path("/path/to/llm-wiki")
state = load_batch_state(repo)

add_pending(state, BatchJob(
    batch_id="batch_abc",
    source_slugs=["sess-1", "sess-2"],
    submitted_at="2026-04-17T10:00:00Z",
))
save_batch_state(repo, state)

# ... later, when you poll and find it done:
mark_completed(state, "batch_abc")
save_batch_state(repo, state)
```

The state file (`.llmwiki-batch-state.json`) is small JSON — safe to
grep, diff, and commit if you want to audit what's been submitted.

## Rate card

From `llmwiki/cache.py :: MODEL_PRICING` (USD per 1 M tokens, as of
v1.1.0):

| Model             | input | cached_input | cache_write | output |
|-------------------|------:|-------------:|------------:|-------:|
| claude-sonnet-4-6 |  3.00 |         0.30 |        3.75 |  15.00 |
| claude-haiku-4    |  0.80 |         0.08 |        1.00 |   4.00 |
| claude-opus-4     | 15.00 |         1.50 |       18.75 |  75.00 |

These are the rates `estimate_cost()` uses. Update them in one place
(`MODEL_PRICING`) when Anthropic publishes new ones.

## What's still to do (v1.2)

- The actual Anthropic backend that wires `CachedPrompt` into
  `client.messages.create(...)`.
- `llmwiki sync --batch` that submits through `message_batches` and
  polls for completion.
- Write-through updating of `MODEL_PRICING` from Anthropic's pricing
  JSON.
- Gemini / OpenAI cache header mapping (separate PR — different
  semantics).

See #50 for the tracking issue.
