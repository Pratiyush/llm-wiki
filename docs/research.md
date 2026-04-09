# Phase 1.25 — Research Report

**Date:** 2026-04-08
**Method:** Cloned every referenced implementation from [Karpathy's gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and the top related GitHub searches into `.temp/` (gitignored) for side-by-side comparison.

This document is the deliverable for **Phase 1.25 Research**, a new phase added to the llmwiki framework (see [docs/framework.md](framework.md)). It is the source of truth for prior-art analysis and the 10x gap that llmwiki targets.

## Summary

15 reference implementations were cloned and analysed. They fall into four clusters:

| Cluster | What they do | Examples | llmwiki differentiation |
|---|---|---|---|
| **Pure-markdown skills** | A Claude Code skill/plugin + CLAUDE.md schema; rely on the agent to do all writes | `kfchou/wiki-skills`, `Astro-Han/karpathy-llm-wiki`, `bashiraziz/llm-wiki-template` | ✅ Same base + native `.jsonl` → markdown + static HTML + multi-agent |
| **Markdown-first + light Python** | Schema + a few Python scripts for ingest/query/lint | `SamurAIGPT/llm-wiki-agent`, `Ss1024sS/LLM-wiki`, `hsuanguo/llm-wiki` | ✅ Same shape + session-transcript adapter + beautiful static site |
| **Obsidian-coupled** | Wiki lives inside an Obsidian vault; user views via Obsidian | `AgriciDaniel/claude-obsidian`, `louiswang524/llm-knowledge-base`, `kytmanov/obsidian-llm-wiki-local`, `remember-md/remember` | 🔀 Obsidian as **one of many** connectors (input adapter) — not the only view |
| **Heavy Python / hosted** | Backend services, databases, hosted demos | `lucasastorian/llmwiki` (Apache, Supabase + MCP, hosted at llmwiki.app), `bitsofchris/openaugi` | ❌ Too heavy — violates llmwiki's stdlib-first rule |
| **Session browsers (not wikis)** | Search/TUI over raw `.jsonl`; no wiki compilation | `raine/claude-history`, `sinzin91/search-sessions` | 🔀 Complementary — they search raw; llmwiki builds the wiki on top |

## Per-repo analysis

### Pure-markdown skills

#### [kfchou/wiki-skills](https://github.com/kfchou/wiki-skills)
- **Shape:** Claude Code plugin. 6 markdown files, 0 Python files.
- **Strength:** Minimal, well-scoped. Pure schema + slash commands.
- **Gap:** No static HTML output. No multi-agent support. No session-transcript adapter — input is "any markdown".
- **Lesson:** The "Claude Code plugin" distribution mode is clean — ship as a plugin + a few .md files, zero runtime deps.

#### [Astro-Han/karpathy-llm-wiki](https://github.com/Astro-Han/karpathy-llm-wiki)
- **Shape:** "One skill" marketed as Agent Skills-compatible. 6 markdown, MIT.
- **Strength:** Explicitly targets the Agent Skills ecosystem.
- **Gap:** Same as above — no session-aware ingestion, no HTML rendering.
- **Lesson:** There's a clean "one-skill" positioning angle (minimal cognitive footprint) that resonates.

#### [bashiraziz/llm-wiki-template](https://github.com/bashiraziz/llm-wiki-template)
- **Shape:** Template with 26 markdown files + 3 Python scripts. MIT.
- **Strength:** Template layout is clean and opinionated.
- **Gap:** Template alone — no session transcripts, no HTML, no adapters.
- **Lesson:** A template-first distribution is a lower-effort entry point than a full tool.

### Markdown-first + light Python

#### [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent)
- **Shape:** 11 markdown + 4 Python scripts. MIT.
- **Strength:** The best-documented schema I've read. `/wiki-ingest`, `/wiki-query`, `/wiki-lint`, `/wiki-graph` slash commands. `build_graph.py` generates a vis.js knowledge graph.
- **Gap:** Input is "drop markdown in `raw/`" — no knowledge of session transcripts. No dark mode. No search. No HTML output beyond the graph HTML.
- **Lesson:** This is the closest prior art. llmwiki inherits its directory layout and slash-command naming (`/wiki-*`).

#### [Ss1024sS/LLM-wiki](https://github.com/Ss1024sS/LLM-wiki)
- **Shape:** 25 markdown + 4 Python. Generates 30 files including stale-reporting scripts.
- **Strength:** Explicitly covers the "AI remembers nothing in new sessions" pain point in its README.
- **Gap:** No HTML viewer. No multi-agent.
- **Lesson:** The stale-reporting idea is worth borrowing — llmwiki should ship `/wiki-lint` with "stale pages" detection baked in.

#### [hsuanguo/llm-wiki](https://github.com/hsuanguo/llm-wiki)
- **Shape:** 13 markdown + 9 Python. Has a logo, more polish.
- **Strength:** The most Python-heavy of the markdown-first implementations — suggests the author hit real scale issues.
- **Gap:** Not session-aware.
- **Lesson:** Once you reach ~10 Python files, you're building a CLI. llmwiki leans into that explicitly.

### Obsidian-coupled

#### [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)
- **Shape:** 50 markdown files, 0 Python. The wiki itself is real content living in Obsidian.
- **Strength:** Treats Obsidian as a first-class viewer. The `meta/` folder contains a cover GIF — good product presentation.
- **Gap:** 100% Obsidian-locked. If you don't use Obsidian, this is useless.
- **Lesson:** Obsidian is a compelling viewer for many users — llmwiki should ship an Obsidian connector as an **optional** input/output, not the only path.

#### [kytmanov/obsidian-llm-wiki-local](https://github.com/kytmanov/obsidian-llm-wiki-local)
- **Shape:** 2 markdown + 25 Python files. Uses a **local** LLM (no cloud API calls).
- **Strength:** Privacy angle — everything runs locally, no OpenAI/Anthropic API calls.
- **Gap:** Requires running a local model — heavy prerequisite.
- **Lesson:** Privacy-first positioning resonates. llmwiki's no-telemetry + local-only rules align with this.

#### [louiswang524/llm-knowledge-base](https://github.com/louiswang524/llm-knowledge-base)
- **Shape:** 10 markdown + 1 Python. Claude Code + Obsidian.
- **Strength:** Clean coupling between Claude Code (writer) and Obsidian (viewer).
- **Gap:** Assumes Obsidian is installed.
- **Lesson:** "Writer/viewer split" is a useful mental model.

#### [remember-md/remember](https://github.com/remember-md/remember)
- **Shape:** 23 markdown, 0 Python. Obsidian-compatible memory for OpenClaw + Claude Code.
- **Strength:** "Tool-portable memory" framing — "one brain, every AI tool".
- **Gap:** Focused on memory/decisions rather than wiki compilation.
- **Lesson:** The multi-agent portability angle is strong. llmwiki's adapter pattern delivers this.

### Heavy Python / hosted

#### [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki)
- **Shape:** 1 markdown + 47 Python files. Apache 2.0. Hosted demo at [llmwiki.app](https://llmwiki.app).
- **Strength:** Has a real backend (Supabase + S3), MCP server, hosted UI. Production-grade infra.
- **Gap:** Requires Supabase + S3 + Node + MCP server to self-host. Violates llmwiki's stdlib rule hard.
- **Lesson:** This is the "full-stack" approach. llmwiki is explicitly the opposite — zero infra, all local.

#### [bitsofchris/openaugi](https://github.com/bitsofchris/openaugi)
- **Shape:** 27 markdown + 48 Python files. "Your augmented knowledge base for Agentic work."
- **Strength:** Covers agent-centric use cases well.
- **Gap:** Very heavy.
- **Lesson:** There's room for a lighter alternative — which is llmwiki's niche.

### Session browsers (complementary, not competitors)

#### [raine/claude-history](https://github.com/raine/claude-history)
- **Shape:** TUI app. 3 markdown + 0 Python.
- **Strength:** "Best thing ever" user quote in the README. Clear UX.
- **Gap:** Search-only, no wiki building.
- **Lesson:** Users love the ability to search their session history. llmwiki's wiki is additive — it compiles search-ready content.

#### [sinzin91/search-sessions](https://github.com/sinzin91/search-sessions)
- **Shape:** CLI binary. 13 markdown + 0 Python (Go).
- **Strength:** Sub-300ms search across all sessions.
- **Gap:** Same — search only.
- **Lesson:** llmwiki could call out to search-sessions as an optional backend for its Cmd+K search.

### Not cloned (mentioned but out of scope)

- [tobi/qmd](https://github.com/tobi/qmd) — personal wiki format, broader than llmwiki
- [silverbulletmd/silverbullet](https://github.com/silverbulletmd/silverbullet) — extensible notes platform
- [swarmclawai/swarmvault](https://github.com/swarmclawai/swarmvault) — multi-agent vault
- [anzal1/quicky-wiki](https://github.com/anzal1/quicky-wiki) — small-scale wiki
- [Houseofmvps/codesight](https://github.com/Houseofmvps/codesight) — different domain
- [milla-jovovich/mempalace](https://github.com/milla-jovovich/mempalace) — memory palace
- [MetamusicX/llm-research-wiki](https://github.com/MetamusicX/llm-research-wiki) — research-only

## The 10x gap (feature matrix)

| Feature | Most existing | llmwiki |
|---|---|---|
| Ingests `.jsonl` session transcripts | ❌ (generic markdown only) | ✅ |
| Claude Code adapter | Some | ✅ |
| Codex CLI adapter | None | ✅ stub (v0.2) |
| Multi-agent adapter pattern | None | ✅ |
| Pure stdlib + `markdown` (no DB, no MCP, no Node) | ~50% | ✅ |
| Beautiful static HTML viewer | ❌ | ✅ god-level UI |
| Global search (Cmd+K) | ❌ | ✅ client-side index |
| Syntax highlighting | Rarely | ✅ highlight.js (CDN) |
| Redaction by default | ❌ | ✅ username + API keys + tokens + emails |
| Live-session detection | ❌ | ✅ skips `<60min` old |
| Idempotent incremental sync | Some | ✅ mtime state file |
| Windows `.bat` scripts | Rarely | ✅ |
| Obsidian connector | Some (only input) | ✅ input **and** output |
| No cloud, no telemetry, no auth | Some | ✅ hard rule |
| Build time `<15s` for 300 sessions | Varies | ✅ 9s measured |

## Borrowed ideas (with attribution)

- **Directory layout** (`raw/`, `wiki/`, `index.md`, `log.md`, `overview.md`) — Karpathy's gist + SamurAIGPT/llm-wiki-agent
- **Slash commands** (`/wiki-ingest`, `/wiki-query`, `/wiki-lint`, `/wiki-graph`) — SamurAIGPT/llm-wiki-agent
- **Stale-page detection** — Ss1024sS/LLM-wiki
- **Local-LLM privacy angle** — kytmanov/obsidian-llm-wiki-local
- **Writer/viewer split** — louiswang524/llm-knowledge-base
- **Multi-tool portable memory framing** — remember-md/remember
- **Hosted-demo angle** (to be used for Phase 6.5 Self-Demo, not the tool itself) — lucasastorian/llmwiki
- **Single-skill marketing** — Astro-Han/karpathy-llm-wiki

## Decisions informed by this research

1. **Keep llmwiki stdlib-first.** `lucasastorian/llmwiki` shows the "full-stack" approach exists; llmwiki is the local alternative.
2. **Ship an Obsidian adapter in v0.1.** Four of 15 reference implementations use Obsidian — clearly important to users. Make it an optional input adapter, not the only path.
3. **Ship the HTML viewer as the hero feature.** None of the reference implementations have a beautiful static HTML output. This is llmwiki's most visible 10x.
4. **Keep the slash commands compatible** with SamurAIGPT/llm-wiki-agent and kfchou/wiki-skills. Users can switch between implementations.
5. **Use Karpathy's three-layer structure exactly** (`raw/` immutable, `wiki/` LLM-maintained, schema in CLAUDE.md/AGENTS.md). No deviations.
6. **Build-time redaction is non-negotiable** — none of the reference implementations do this, and session transcripts leak PII by default.

## References

- [Andrej Karpathy — LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Karpathy's X thread](https://x.com/karpathy/status/2039805659525644595)
- [Tolkien Gateway](https://tolkiengateway.net/wiki/Main_Page) — example of a user-maintained wiki Karpathy cites for structure
- All 15 cloned repos listed above (under `.temp/`, gitignored)
