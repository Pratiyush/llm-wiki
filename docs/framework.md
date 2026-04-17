# llmwiki Framework — Building an Agent-Native Dev Tool

> **Adapted from** the maintainer's "Open Source Project Framework v4.0" (local reference — kept outside the public repo).
>
> **Extensions** specific to llmwiki and any tool in this class (dev tools that ingest from AI coding agents):
>
> 1. **Agent-Aware pipeline** (Phase 1.75)
> 2. **Adapter Contribution flow** (Phase 5.25)
> 3. **Self-Demo pattern** (Phase 6.5)
> 4. **Living-Knowledge loop** (Phase 7.5)
> 5. **Schema-Versioning rules** (cross-cutting)
> 6. **Privacy-First rules** (cross-cutting)
> 7. **Performance Budget** (cross-cutting)
> 8. **Dogfooding Meta-Loop** (cross-cutting)

This document is both the **spec for how llmwiki is built** and the **contribution guide for anyone extending it**. It is the source of truth for what "done" means at each phase.

---

## The Pipeline (extended)

```
0 CAPTURE  →  1 VALIDATE  →  1.25 RESEARCH  →  1.5 STEERING  →  1.75 AGENT SURVEY
  →  2 BRAND  →  3 STRUCTURE  →  4 CONTENT  →  5 CONTRIBUTION  →  5.25 ADAPTER FLOW
  →  5.5 PRE-LAUNCH QA  →  6 LAUNCH  →  6.5 SELF-DEMO  →  7 GROW
  →  7.5 LIVING KNOWLEDGE  →  8 MAINTAIN
```

**Five** new phases slot into the parent pipeline. **Kiro-style spec-driven** overlay applies to every phase (see `.kiro/steering/` for always-loaded rules).

The new phases are:

| Phase | New? | Why it exists | Deliverable |
|---|---|---|---|
| 1.75 Agent Survey | NEW | Agent-native tools need to know the `.jsonl` / session store schema for every agent they claim to support | Per-agent compatibility matrix + test fixtures |
| 5.25 Adapter Flow | NEW | Extensible agent tools need a contract for community-contributed adapters | `docs/adapter-contract.md` + PR template |
| 6.5 Self-Demo | NEW | Dev tools that produce browsable HTML have a killer demo surface — the tool's own dev history | Public GitHub Pages site built from the repo's own sessions |
| 7.5 Living Knowledge | NEW | The wiki built during development IS a growth engine — publish it and it sells the tool for you | Public wiki updating on every release |

---

## Phase 0 — Capture

Same as parent framework. See `idea-brief.md` at the repo root for llmwiki's capture.

**Gate to Phase 1**: idea-brief.md exists and names the target users + the one non-obvious mechanism that makes this 10x.

---

## Phase 1 — Validate

Same scoring (/25). llmwiki scored **22/25** on 2026-04-08 (see `_progress.md`).

| Dimension | Score | Note |
|---|---|---|
| Gap | 5/5 | No existing tool bridges `.jsonl` → Karpathy wiki |
| Quality gap | 5/5 | Existing implementations require Node + Postgres + MCP; we require only stdlib + one pip install |
| Audience | 4/5 | Every Claude Code user is a potential user; niche but growing fast |
| Effort | 4/5 | v0.1 ships in a day; v1.0 in a week |
| Personal fit | 4/5 | Author already has 278+ session transcripts; uses the tool daily |

**Kill threshold**: < 13/25 → kill. 13–19 → research further. 20+ → build.

---

## Phase 1.5 — Project Steering

**llmwiki steering decisions** (locked on 2026-04-08):

| Decision | Choice | Rationale |
|---|---|---|
| Runtime dep floor | Python 3.9+ stdlib + `markdown` | Matches oldest common macOS system Python |
| Optional deps | `pypdf` (PDF ingestion) | Detected, not required |
| No-network by default | True | Privacy + offline-first |
| Binding default | `127.0.0.1` only | Privacy-first — user must opt-in to LAN |
| Redaction default | ON | Username, API keys, tokens, emails — all redacted |
| Config file | JSON, single file | TOML excluded because `tomllib` is 3.11+ only |
| Distribution | Git-native (clone + `./setup.sh`) | v0.1. pip-installable from git in v0.2 |
| Branch name | `master` | Matches author's other projects |
| License | MIT | Permissive, widely understood |
| Telemetry | None, ever | Trust the user's machine |
| GPL/AGPL deps | Forbidden | Keep the tool MIT-compatible end-to-end |

---

## Phase 1.75 — Agent Survey (NEW)

Before Phase 2 Brand, any tool targeting AI coding agents must complete this survey:

### Agent compatibility matrix

| Agent | Session store | File pattern | Record types seen | Tested version | Adapter status |
|---|---|---|---|---|---|
| Claude Code | `~/.claude/projects/<proj>/` | `<uuid>.jsonl` + `<uuid>/subagents/agent-*.jsonl` | `user`, `assistant`, `tool_use`, `tool_result`, `queue-operation`, `file-history-snapshot`, `progress` | 2.1.87 | ✅ Production |
| Codex CLI | `~/.codex/sessions/` (TBC) | TBC | TBC | TBC | 🚧 Stub |
| Gemini CLI | TBC | TBC | TBC | TBC | ⏳ Planned |
| OpenCode | `~/.opencode/` (TBC) | TBC | TBC | TBC | ⏳ Planned |

### Test fixture requirements

Every claimed agent must ship:

1. **At least one fixture `.jsonl`** under `tests/fixtures/<agent>/` (synthetic or heavily redacted).
2. **A snapshot test** that converts the fixture and asserts the output matches `tests/snapshots/<agent>/*.md`.
3. **A schema version constant** pinned in the adapter: `SUPPORTED_SCHEMA_VERSIONS = ["..."]`.

Without all three, the adapter ships as a **stub** (imports cleanly, logs "not yet tested", does not convert).

### Graceful degradation rule

When an adapter encounters a record `type` it doesn't know:
- **Skip it silently** — don't crash the build
- **Log at DEBUG level**, not WARN or ERROR
- **Never drop user-visible content** — user prompts and assistant text are always rendered even if the wrapping record is unknown

### Gate to Phase 2

1.75 closes when:
- [x] Matrix row exists for every agent the README claims to support
- [x] Test fixtures exist for every "Production" adapter
- [x] Stub adapters are clearly marked in the README and CHANGELOG

---

## Phase 2 — Brand

Same as parent. llmwiki brand artifacts:

- **Name**: `llmwiki` (lowercase, one word)
- **Tagline**: "LLM-powered knowledge base from your Claude Code and Codex CLI sessions"
- **README header**: License + Python + Claude Code badge + Codex badge
- **LICENSE**: MIT

---

## Phase 3 — Structure

Same as parent. llmwiki layout is defined in `docs/architecture.md`. Key invariants:

```
llmwiki/                      # Python package (renamed from tools/)
├── __init__.py
├── __main__.py               # enables `python3 -m llmwiki`
├── cli.py                    # argparse entry
├── convert.py                # .jsonl → markdown
├── build.py                  # markdown → HTML
├── serve.py                  # HTTP server
├── adapters/
│   ├── __init__.py           # registry
│   ├── base.py               # BaseAdapter
│   ├── claude_code.py
│   └── codex_cli.py
└── templates/
    ├── style.css             # embedded as Python string for single-file rendering
    └── script.js             # embedded as Python string

raw/, wiki/, site/            # [gitignored] data layers
bin/, docs/, examples/        # user-facing
.claude/commands/             # Claude Code slash commands (committed)
.github/workflows/            # CI (committed)
```

### Hard rule — no dual Python package

There is exactly ONE `llmwiki/` directory that is a Python package. Tools live inside it, not alongside it in a `tools/` sibling. (This is a lesson from the earlier llm-wiki workspace which had both.)

---

## Phase 4 — Content

Same as parent. For llmwiki specifically:

- **CSS/JS are Python string constants** inside `build.py` — single-file rendering, no template loader, no file watching complexity.
- **No templates directory as separate files** (the `templates/` subdirectory is a stub for future split when the files grow beyond 2000 lines).
- **Syntax highlighting** uses highlight.js loaded from a CDN at view time. No build-time syntax parsing required.

### Performance Budget (cross-cutting rule)

| Metric | Target | Measured 2026-04-08 |
|---|---|---|
| Cold build time (300 sessions) | < 15s | 9s |
| Incremental build time (no changes) | < 1s | 0.4s |
| Total static-site size (300 sessions) | < 50 MB | 24 MB |
| Per-session HTML page | < 500 KB | avg 50 KB |
| CSS + JS bundle | < 100 KB | 12 KB |

If any metric exceeds its budget, the offending change is blocked or must be preceded by a measurement + optimisation PR.

### Privacy-First rules (cross-cutting)

1. **Redaction is on by default.** Username, API keys, tokens, and emails are redacted at the converter layer, before anything hits `raw/`.
2. **No telemetry, ever.** Not even anonymised "which adapter is used". The tool never calls home.
3. **Binding default is `127.0.0.1`.** LAN or public binding requires an explicit `--host 0.0.0.0`.
4. **No cloud features.** No auth, no accounts, no sync. Everything is local.
5. **Config never stores secrets.** The config file only stores regex patterns and truncation limits.
6. **CI must pass `grep -r "pratiyush1" site/` with zero hits** on any build produced from fixtures.

### Schema-Versioning rules (cross-cutting)

1. Every adapter declares `SUPPORTED_SCHEMA_VERSIONS: list[str]`.
2. When an adapter sees a session from an unlisted version, it logs DEBUG and continues (graceful degradation).
3. Test fixtures are committed per-version — `tests/fixtures/claude_code/v2.1/*.jsonl`.
4. Major agent version bumps get their own adapter file (never a monolithic if/elif chain).

---

## Phase 5 — Contribution Setup

Same as parent plus one addition: **adapter contribution flow** (Phase 5.25).

### PR rules (reiterated from parent)

- git config user.name: `Pratiyush`
- git config user.email: `pratiyush1@gmail.com`
- No AI co-authored-by lines
- One PR per concern
- Small commits (one file group per commit)

### Library-style two-workflow CI

From parent framework. For llmwiki:

- **`ci.yml`** — lint + build smoke test on push + PR to `master`. Never publishes.
- **`pages.yml`** — deploys the self-demo site (see Phase 6.5) on tag push.

---

## Phase 5.25 — Adapter Contribution Flow (NEW)

An extensible agent tool needs a predictable way for community contributors to add support for a new agent.

### Contract

To add a new agent adapter, a PR must include:

1. **One file under `llmwiki/adapters/<agent>.py`** that:
   - Subclasses `BaseAdapter`
   - Registers itself via `@register("<agent>")`
   - Sets `session_store_path` to the agent's default location(s)
   - Declares `SUPPORTED_SCHEMA_VERSIONS`
   - Overrides `derive_project_slug()` if needed

2. **At least one fixture** under `tests/fixtures/<agent>/minimal.jsonl` (synthetic or heavily redacted).

3. **One snapshot test** under `tests/snapshots/<agent>/minimal.md`.

4. **One test** under `tests/test_<agent>_adapter.py` that loads the fixture, runs the converter, and diffs against the snapshot.

5. **One documentation page** at `docs/adapters/<agent>.md` explaining:
   - What session store path the adapter reads
   - How to verify the adapter sees sessions (`python3 -m llmwiki adapters`)
   - Known format quirks

6. **A CHANGELOG entry** under `## [Unreleased]`.

7. **One line in `README.md`** under "Works with".

### Review checklist

- [ ] Adapter declares `SUPPORTED_SCHEMA_VERSIONS`
- [ ] Fixture file is under 50 KB and contains no real PII
- [ ] Snapshot test passes locally
- [ ] `docs/adapters/<agent>.md` exists and is linked from README
- [ ] Graceful degradation: unknown record types are skipped, not crashed on
- [ ] No new runtime deps introduced

### Gate to Phase 5.5

Adapter-flow is met when the checklist above is automatable (a GitHub Actions workflow enforces it on every PR touching `llmwiki/adapters/**`).

---

## Phase 5.5 — Pre-Launch QA

Same as parent. For llmwiki specifically:

- [ ] Run `./setup.sh` on a pristine git clone
- [ ] Run `./sync.sh && ./build.sh && ./serve.sh`
- [ ] Visit http://127.0.0.1:8765/ and click through 5 random session pages
- [ ] Cmd+K opens the command palette
- [ ] `/` focuses the search bar
- [ ] Dark mode toggle works and persists
- [ ] Copy-code button works on a code block
- [ ] Copy-as-markdown button works on a session page
- [ ] `grep -r pratiyush1 site/` returns zero hits (privacy check)
- [ ] All links in README return HTTP 200
- [ ] `python3 -m llmwiki --version` prints the version
- [ ] `python3 -m llmwiki adapters` lists claude_code as available

---

## Phase 6 — Launch

Same as parent:

1. `git init`
2. Atomic commits per file group (README separate from code, tests separate from adapters, etc.)
3. `gh repo create Pratiyush/llmwiki --public`
4. `git push -u origin master`
5. `git tag v0.1.0 && git push origin v0.1.0`
6. Create GitHub Release (mark as pre-release for 0.x)

---

## Phase 6.5 — Self-Demo (NEW)

**llmwiki's killer demo is its own repo.**

Every dev tool that produces browsable output should publish its own dev history as the demo. The pattern:

1. **On tag push**, CI:
   a. Runs the tool against the author's own session transcripts (stored as an encrypted test corpus OR synthetic fixtures)
   b. Builds the HTML site to `site/`
   c. Publishes to GitHub Pages
2. The GitHub Pages URL becomes the README's demo link.
3. Every release updates the demo automatically.
4. Visitors SEE the exact output they'd get. No screenshots, no "look here's what it looks like on my machine".

For **privacy reasons**, llmwiki's self-demo uses a **synthetic corpus** under `tests/fixtures/demo/`, not the author's real session history. The fixtures are hand-curated, cover all UI states (short sessions, long sessions, sub-agents, code blocks, tool calls, errors), and are committed to the repo.

### Gate to Phase 7

Self-demo is closed when:
- [x] `tests/fixtures/demo/` has 10+ representative sessions
- [ ] `.github/workflows/pages.yml` builds and publishes on tag push
- [ ] The README's demo link is a working URL

---

## Phase 7 — Grow

Same as parent. Platform strategies for a dev tool:

| Platform | Angle |
|---|---|
| Reddit r/ClaudeAI | "I built a local tool that turns all your Claude Code sessions into a Karpathy-style wiki" |
| Reddit r/programming | "Self-hosted knowledge base from your AI coding sessions, no servers needed" |
| Hacker News | "Show HN: llmwiki — Turn your coding agent session history into a searchable wiki" |
| X/Twitter | Thread: screenshot → demo URL → install command → link |
| Dev.to | Long-form: "I have 278 Claude Code sessions. I built this to browse them." |
| LinkedIn | "Learning from your own work" framing |

---

## Phase 7.5 — Living Knowledge (NEW)

**The wiki built during development IS a growth engine.** Publish it.

- The author's own `wiki/` (synthetic or hand-curated) becomes a public knowledge base at `https://pratiyush.github.io/llmwiki/wiki/`.
- Every release refreshes the public wiki with new insights, decisions, and patterns extracted from dev sessions.
- Visitors who land on the demo can also browse the **living documentation of how the tool is built** — a form of meta-transparency that doubles as SEO.

### Operational rules

1. **No real PII.** Use the same synthetic corpus as Phase 6.5 Self-Demo.
2. **Opt-in.** The `pages.yml` workflow only publishes to Pages when a tag is pushed, not on every commit.
3. **The public wiki and the release notes cross-link.** Every release's changelog links to the relevant wiki page.
4. **Feedback loop.** Community feedback on wiki pages (via GitHub Issues) feeds back into the framework.

---

## Phase 8 — Maintain

Same as parent plus agent-specific additions:

### Monthly checklist

- [ ] Check Claude Code / Codex CLI release notes for schema changes
- [ ] Re-run test fixtures against latest CLI version
- [ ] Update `SUPPORTED_SCHEMA_VERSIONS` if compatibility confirmed
- [ ] Bump CHANGELOG
- [ ] Re-run pre-launch QA checklist
- [ ] Review open issues labelled `adapter:*`

### Schema-change response playbook

When an agent ships a new `.jsonl` schema:

1. Create a fresh fixture from a real (redacted) session
2. Run the converter; note any crashes or data-loss
3. If graceful degradation works: add the version to `SUPPORTED_SCHEMA_VERSIONS`, commit the fixture, done
4. If not: open an issue, tag `adapter:<agent>`, block the release until fixed
5. If the change is breaking: ship a new adapter file (`claude_code_v3.py`) alongside the old one, route by version

---

## Dogfooding Meta-Loop (cross-cutting)

**llmwiki tracks its own development with llmwiki.**

- Every dev session on llmwiki is already being captured by Claude Code.
- `./sync.sh` pulls those sessions into `raw/sessions/llmwiki/`.
- The author runs `./build.sh` and reads the output to validate the tool on its own dev history.
- Insights (bugs, UX issues, missing features) get extracted into `tasks.md`.
- The loop closes: the tool's own output drives the tool's own backlog.

This is only possible because the tool is self-referential by design — it's a dev tool that browses dev sessions, built during dev sessions.

---

## Summary of extensions over the parent framework

| Phase / Rule | Added | What it gives you |
|---|---|---|
| 1.75 Agent Survey | ✅ | Predictable adapter compatibility tracking |
| 5.25 Adapter Flow | ✅ | Community can extend the tool without the author's intervention |
| 6.5 Self-Demo | ✅ | Zero-effort landing-page demo from CI |
| 7.5 Living Knowledge | ✅ | The dev wiki doubles as marketing + meta-documentation |
| Schema-Versioning rules | ✅ | Graceful degradation when upstream agents change format |
| Privacy-First rules | ✅ | No telemetry, no network, no PII by default |
| Performance Budget | ✅ | Budget-enforced build pipeline |
| Dogfooding Meta-Loop | ✅ | Tool improves itself from its own output |

None of these violate the parent framework; they extend it with patterns specific to **agent-native dev tools** — a category that the parent framework's `Curated Lists / Libraries / Marketplaces / Dev Tools` typology didn't cover.

Future projects in this category (a Cursor wiki, a Cline session browser, a multi-agent unified viewer) should inherit this document and extend it further.
