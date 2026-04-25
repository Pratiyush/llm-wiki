---
title: "Cache Pricing"
type: concept
tags: [llm, pricing, prompt-cache]
last_updated: 2026-04-23
sources: []
confidence: 0.55
lifecycle: draft
---

# Cache Pricing

The per-token cost of reading from an LLM provider's prompt cache,
typically priced at ~10% of the regular input rate. Providers charge a
one-time cache-write fee (often ~25% premium over input) but every
subsequent read is the discounted cache-read rate.

For [[AgenticWorkloads]] that re-send a large, stable prefix on every
turn, caching flips the cost curve: total spend becomes dominated by
the cheap cache-reads rather than fresh input tokens.

## Reference rates (2026-04)

| Provider | Input | Cache write | Cache read |
|---|---|---|---|
| Anthropic Claude Sonnet 4 | $3.00/1M | ~$3.75/1M | $0.30/1M |

## Connections

- [[ClaudeSonnet4]] — one of the more aggressively priced caches
- [[AgenticWorkloads]] — the workload class that benefits most
