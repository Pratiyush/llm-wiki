---
title: "Slash commands reference"
type: navigation
docs_shell: true
---

# Slash commands reference

Every `/wiki-*` (plus governance commands) in `.claude/commands/`,
what it does, what it runs under the hood, and a realistic invocation
example. Use these inside **Claude Code** — Codex CLI picks the same
files up via `install-skills`.

Summary of **18 commands in 4 groups**:

| Group | Commands |
|---|---|
| **Wiki pipeline** (14) | `/wiki-init` `/wiki-sync` `/wiki-ingest` `/wiki-query` `/wiki-update` `/wiki-lint` `/wiki-candidates` `/wiki-synthesize` `/wiki-graph` `/wiki-reflect` `/wiki-build` `/wiki-serve` `/wiki-export-marp` `/wiki-all` |
| **Governance / maintainer** (4) | `/maintainer` `/release` `/review-pr` `/triage-issue` |

---

## Decision tree: which tool runs when?

### CLI vs slash

| You want to… | Use |
|---|---|
| …run a check in CI, a cron job, or a shell script | **CLI** (`python3 -m llmwiki …`) |
| …chain commands with `&&` / pipe to `jq` | **CLI** |
| …have the model read output + take follow-up actions | **slash** (inside Claude Code / Codex) |
| …answer a free-form question ("what did I decide about X?") | **slash** (`/wiki-query`) |
| …do one-shot builds, serves, graph generation | either — slashes wrap the CLI |

**Rule of thumb:** if the output is for *you* to read + act on manually,
use the CLI. If the output should feed back into an LLM turn, use the
slash — the model sees the full stdout and can chain into the next step.

### Eval vs lint

Two different QA surfaces that are easy to confuse:

| Command | Checks | Severity model | When to run |
|---|---|---|---|
| [`llmwiki lint`](../reference/cli.md#lint--run-13-wiki-quality-rules) / `/wiki-lint` | **Wiki content quality** — frontmatter completeness, `[[wikilink]]` integrity, orphans, duplicate titles, stale pages, cache-tier consistency, tag-topic convention, stale references | 15 rules with `error` / `warning` / `info` severities; `--fail-on-errors` exits non-zero only on errors | After every `/wiki-sync` or `/wiki-build` |
| [`llmwiki eval`](../reference/cli.md#eval--structural-eval-checks-over-wiki) | **Structural corpus health** — site-wide metrics (total pages, orphan ratio, avg outbound links, broken-link rate, duplicate-slug rate, content-length distribution) | Pass / fail against configurable thresholds | In CI, weekly, or when comparing two wiki snapshots |

In plain English: **lint** checks each page against its contract;
**eval** checks the whole wiki against health thresholds.  A page
passing lint doesn't mean the corpus passes eval, and vice versa.

Reach for `lint` first when something looks wrong with a specific
page.  Reach for `eval` when you want to compare two builds (is the
wiki trending healthier? getting more orphans?).

---

## Wiki pipeline

### `/wiki-init`

**What:** scaffolds an empty llmwiki — creates `raw/`, `wiki/`, `site/`
and seeds `wiki/index.md`, `wiki/log.md`, `wiki/overview.md`, plus the
nine navigation files (`CRITICAL_FACTS.md`, `MEMORY.md`, `SOUL.md`,
`hints.md`, `hot.md`, `dashboard.md`).

**Wraps:** `python3 -m llmwiki init`.

**When to use:** first time in a fresh repo, or after deleting `wiki/`
to start over.

**Example:**

```
/wiki-init
```

Claude Code will respond by running init and surfacing which files
were seeded.

---

### `/wiki-sync`

**What:** convert new Claude Code (+ Codex + Cursor + etc.) `.jsonl`
sessions into markdown under `raw/sessions/`, then ingest into `wiki/`.

**Wraps:** `python3 -m llmwiki sync`.

**Arguments Claude may pass through:** `--dry-run`, `--since`,
`--project`, `--force`, `--vault`. Say any of them in natural language
— "sync but only sessions from this week" becomes
`--since $(date -v-7d +%Y-%m-%d)`.

**When to use:** at the end of each coding block. Also the only command
that triggers auto-ingest of new pages into `wiki/`.

**Example:**

```
/wiki-sync
/wiki-sync only my llm-wiki project
/wiki-sync but don't auto-build afterwards
/wiki-sync into my Obsidian vault at ~/Documents/Obsidian Vault
```

**Expected output (narrated):**

```
==> claude_code: 3 new sessions since last sync
✓ wrote 3 pages under raw/sessions/
✓ ingested into wiki/sources/
✓ auto-build: site/ rebuilt (690 HTML files)
```

---

### `/wiki-ingest <path>`

**What:** ingest **one** source document or folder into `wiki/`. Reads
the file, creates / updates the matching `wiki/sources/<slug>.md`,
extracts entities into `wiki/entities/`, creates candidates in
`wiki/candidates/` for anything it hasn't seen before.

**Wraps:** the Ingest Workflow in `CLAUDE.md` (no single CLI — it's a
slash-command-driven workflow that the model orchestrates).

**When to use:** you dropped a source file manually (a PDF, a Jira
ticket export, a meeting transcript) and want it in the wiki.

**Examples:**

```
/wiki-ingest raw/sources/2026-04-17-incident.md
/wiki-ingest raw/jira/
/wiki-ingest ~/Downloads/meeting-transcript.vtt
```

---

### `/wiki-query <question>`

**What:** answer a question from the wiki. Reads `wiki/index.md` +
`wiki/overview.md` + any `cache_tier: L1` pages, then walks relevant
source / entity / concept pages and synthesises an answer with inline
`[[wikilinks]]` back to the originals.

**Wraps:** the Query Workflow in `CLAUDE.md`.

**When to use:** "have I solved this before?" / "when did I add X?" /
"which sessions touched Y?".

**Examples:**

```
/wiki-query when did I add the lint rules?
/wiki-query which agent did I use for refactoring the cache-tier module?
/wiki-query summarize every session about Obsidian integration
```

**Save prompt:** if the answer runs 3+ paragraphs, Claude will offer to
save it under `wiki/syntheses/<slug>.md`.

---

### `/wiki-update <page>`

**What:** surgically edit one wiki page without re-ingesting. Useful
for fixing broken wikilinks, updating stale frontmatter, adding a
missing `## Connections` line.

**When to use:** lint flagged something, you know the fix, you don't
want to re-run sync.

**Example:**

```
/wiki-update wiki/entities/RAG.md add a Connections section linking to Karpathy and llm-wiki
```

---

### `/wiki-lint`

**What:** run every registered lint rule (15 at last count: 8
structural + 3 LLM-powered + `stale_candidates` (#51) +
`cache_tier_consistency` (#52) + `tags_topics_convention` (#302) +
`stale_reference_detection` (#303)). The live number is printed by
`llmwiki lint --help`.

**Wraps:** `python3 -m llmwiki lint`.

**Rules, in order:**

1. `frontmatter_completeness`
2. `frontmatter_validity`
3. `link_integrity`
4. `orphan_detection`
5. `content_freshness`
6. `entity_consistency`
7. `duplicate_detection`
8. `index_sync`
9. `contradiction_detection` *(LLM)*
10. `claim_verification` *(LLM)*
11. `summary_accuracy` *(LLM)*
12. `stale_candidates`
13. `cache_tier_consistency`
14. `tags_topics_convention` *(G-16 · #302)*
15. `stale_reference_detection` *(G-17 · #303)*

**Example:**

```
/wiki-lint
/wiki-lint include LLM-powered rules
/wiki-lint just the link_integrity rule
```

---

### `/wiki-synthesize`

**What:** call the configured LLM backend on every new `raw/sessions/*.md`
to produce `wiki/sources/<slug>.md`.

**Wraps:** `python3 -m llmwiki synthesize` (respects the
`synthesis.backend` key in `sessions_config.json` — `dummy` / `ollama`
and, in-progress on #315, `claude-api`).

**Natural-language flags Claude translates:**

| You say | Runs |
|---|---|
| "just show me what it would cost" | `synthesize --estimate` |
| "preview without writing" | `synthesize --dry-run` |
| "check the backend is reachable" | `synthesize --check` |
| "re-synthesize everything" | `synthesize --force` |

**Example:**

```
/wiki-synthesize
/wiki-synthesize with a cost estimate
/wiki-synthesize force a re-run of every source
```

---

### `/wiki-candidates`

**What:** triage pending candidates — `promote`, `merge`, or `discard`.

**Wraps:** `python3 -m llmwiki candidates list` + follow-ups.

**When to use:** `/wiki-lint` reported a `stale_candidates` info line,
or `/wiki-sync` produced new `wiki/candidates/*.md` files.

**Example:**

```
/wiki-candidates
```

Claude will walk the queue one at a time and offer actions per
candidate.

---

### `/wiki-graph`

**What:** build the knowledge graph. Nodes = wiki pages, edges =
`[[wikilinks]]`. Emits `graph/graph.json` + `graph/graph.html`.

**Wraps:** `python3 -m llmwiki graph`.

**Example:**

```
/wiki-graph
```

Then open `site/graph.html` (auto-copied from `graph/graph.html` during
build) or the compiled URL in the served site.

---

### `/wiki-reflect`

**What:** higher-order self-reflection pass over the whole wiki. Looks
for gaps, patterns, duplicated-topic clusters, areas where a synthesis
page would help.

**No CLI wrapper** — it's a model-orchestrated workflow that reads the
index + overview + sample of pages and outputs suggestions.

**Example:**

```
/wiki-reflect
```

Use sparingly; it's the most token-heavy command.

---

### `/wiki-build`

**What:** regenerate the static HTML site.

**Wraps:** `python3 -m llmwiki build`.

**When to use:** after manual edits to `wiki/`, or when you want to see
a fresh site without running the full sync pipeline.

**Example:**

```
/wiki-build
/wiki-build to ~/public_html
/wiki-build in tree search mode
```

---

### `/wiki-serve`

**What:** start a local HTTP server for the built site.

**Wraps:** `python3 -m llmwiki serve`.

**Example:**

```
/wiki-serve
/wiki-serve on port 9000
```

The server is local-only (`127.0.0.1`) by default. Say "on my LAN" and
Claude will pass `--host 0.0.0.0`.

---

### `/wiki-export-marp`

**What:** generate a Marp slide deck from wiki pages matching a topic.

**Wraps:** `python3 -m llmwiki export-marp --topic …`.

**Example:**

```
/wiki-export-marp topic "cache tiers"
/wiki-export-marp topic Karpathy save to ~/slides/karpathy.marp.md
```

---

### `/wiki-all`

**What:** run the full pipeline end-to-end — build → graph → export all → lint.

**Wraps:** `python3 -m llmwiki all`.

**When to use:** after `/wiki-sync`, when you want a CI-ready site in one shot
instead of chaining `/wiki-build` + `/wiki-graph` + `/wiki-lint` yourself.

**Example:**

```
/wiki-all
/wiki-all --graph-engine builtin
/wiki-all --skip-graph --strict
```

Pass `--strict` to turn any lint warning into a non-zero exit, which is
exactly what CI wants. Pass `--skip-graph` or `--graph-engine builtin`
when the optional Graphify backend is not installed.

---

## Governance / maintainer

### `/maintainer`

Meta-skill that loads all llmwiki governance docs (`CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md`, `docs/maintainers/*`) and exposes the three
maintainer slash commands below.

Use before doing anything governance-related.

### `/release`

Walk through the llmwiki release process step by step — tag, changelog
cut, GitHub Release note, PyPI publish (via OIDC), Homebrew tap bump,
Docker image push.

### `/review-pr`

Run the canonical llmwiki code review against a pull request and post
findings.

**Example:**

```
/review-pr 265
```

Reads the PR via `gh pr view` + `gh pr diff`, applies the review
checklist from `docs/maintainers/`, posts inline comments.

### `/triage-issue`

Apply labels + milestone + priority to a new GitHub issue using the
llmwiki triage rules.

**Example:**

```
/triage-issue 280
```

---

## How the slash commands get installed

The repo ships `.claude/commands/*.md` — Claude Code picks them up
automatically when it opens the repo (no separate install step).

For **Codex CLI / Cursor / Gemini CLI / other agents**, copy the
`.claude/commands/wiki-*.md` files into the corresponding skill
directory for that agent (typically `.codex/skills/` or
`.agents/skills/`) — the file format is portable across agents.

---

## Extending

To add a new slash command:

1. Create `.claude/commands/wiki-<name>.md` with a one-line docstring
   on line 1 (that's the summary Claude Code surfaces).
2. Describe the workflow in prose. Reference existing CLI commands
   rather than embedding shell in the body.
3. Run `/wiki-lint` — the `docs/reference/` guardrail test (see
   `tests/test_docs_structure.py`) will pick up the new command.
4. Document it here; the CI guard requires every `.claude/commands/*.md`
   to have a matching entry.

---

## Related

- **[CLI reference](cli.md)** — the underlying `python3 -m llmwiki …` surface.
- **[UI reference](ui.md)** — every screen on the compiled site, with what's reachable from where.
- **[Tutorial 03 — Use with Claude Code](../tutorials/03-use-with-claude-code.md)** — the minimum daily loop built on these commands.
