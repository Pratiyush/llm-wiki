---
title: "Session: rss-feed-and-sitemap — 2026-03-25"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-03-25
source_file: raw/sessions/demo-blog-engine/2026-03-25-rss-feed-and-sitemap.md
sessionId: demo-000000000000000000000000000003
slug: rss-feed-and-sitemap
project: demo-blog-engine
started: 2026-03-25T10:00:00+00:00
ended: 2026-03-25T11:30:00+00:00
cwd: /Users/demo/code/demo-blog-engine
gitBranch: feat/feeds
permissionMode: default
model: claude-sonnet-4-6
user_messages: 3
tool_calls: 9
tools_used: [Read, Write, Bash]
tool_counts: {"Write": 4, "Read": 3, "Bash": 2}
token_totals: {"input": 4800, "cache_creation": 7200, "cache_read": 18000, "output": 2400}
turn_count: 3
hour_buckets: {"2026-03-25T10": 6, "2026-03-25T11": 3}
duration_seconds: 5400
is_subagent: false
---

# Session: rss-feed-and-sitemap — 2026-03-25

**Project:** `demo-blog-engine` · **Branch:** `feat/feeds` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Emitted `public/rss.xml` and `public/sitemap.xml` during the build. Both are pure string templates — no XML library needed — escaped via a tiny `xml_escape` helper. Added the feed URL to the `<head>` of every post page.

## Conversation

### Turn 1 — User

Add RSS 2.0 + sitemap.xml generation. Keep dependencies light.

### Turn 1 — Assistant

Wrote `src/feeds.rs` with two functions:

- `build_rss(posts: &[Post]) -> String`
- `build_sitemap(posts: &[Post], base_url: &str) -> String`

Both return strings which `main.rs` writes to `public/`. Escaping goes through a tiny `xml_escape` function that handles `<`, `>`, `&`, `"`, `'`.

**Tools used in this turn:**
- `Write`: `src/feeds.rs` (5-line preview)
- `Edit`: `src/main.rs` — added `feeds::build_rss` call
- `Bash`: `cargo test` — exit 0

### Turn 2 — User

Ship it.

### Turn 2 — Assistant

Committed. Added `<link rel="alternate" type="application/rss+xml" href="/rss.xml">` to the post template.

**Tools used in this turn:**
- `Write`: `templates/post.html` (5-line preview)

## Connections

- [[demo-blog-engine]] — project
- [[RSS]] — concept
- [[Sitemap]] — concept
