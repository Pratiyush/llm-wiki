---
title: "03 · Use with Claude Code"
type: tutorial
docs_shell: true
---

# 03 · Use with Claude Code

**Time:** 10 minutes
**You'll need:** A working `llmwiki` CLI and Claude Code installed (sessions at `~/.claude/projects/`).
**Result:** A day-to-day workflow where every Claude Code session is auto-ingested into the wiki and queryable via slash commands.

---

## Why this matters

Claude Code is the source of gravity for most llmwiki users. This tutorial
locks in the habits that keep your wiki current: a single
`/wiki-sync` after a coding session and a `/wiki-query` when you need
to answer "wait, when did I solve this before?"

---

## Step 1 — Confirm the adapter sees your sessions

```bash
python3 -m llmwiki adapters | grep claude_code
```

Expected:

```
claude_code       yes       ✓            Claude Code — reads ~/.claude/projects/
```

If the `configured` column is `-`, Claude Code hasn't written any sessions
yet. Run `claude` once and retry.

See **[`docs/adapters/claude-code.md`](../adapters/claude-code.md)** for the full adapter spec
(project-slug derivation, sub-agent handling, filtering rules).

## Step 2 — Install the slash commands

llmwiki ships slash commands under `.claude/commands/` in the repo. Claude
Code picks them up automatically when you open the llm-wiki project.

Verify:

```bash
ls .claude/commands/
```

You should see:

```
wiki-build.md      wiki-graph.md      wiki-ingest.md     wiki-lint.md
wiki-query.md      wiki-review.md     wiki-serve.md      wiki-sync.md
wiki-update.md     wiki-reflect.md
```

Each is a single-file command spec. Claude Code reads the docstring and
renders it when you type `/` in the chat.

## Step 3 — Run `/wiki-sync` after a coding session

In Claude Code, type:

```
/wiki-sync
```

Under the hood, the slash command executes:

```bash
python3 -m llmwiki sync        # convert new .jsonl → raw/
# then: auto-ingest + auto-build (configurable in sessions_config.json)
```

Expected output (the assistant will narrate each step):

```
==> claude_code: 3 new sessions since last sync
✓ wrote 3 pages under raw/sessions/
✓ ingested into wiki/sources/ (2 new entities, 1 new concept)
✓ auto-build: site/ rebuilt (690 HTML files)
```

Run this at the end of a work session. It takes < 5 s for the incremental
case.

## Step 4 — Query the wiki

```
/wiki-query when did I add the lint rules?
```

Claude Code reads `wiki/index.md` + `wiki/overview.md`, walks the relevant
pages, and gives you a synthesised answer with inline `[[wikilinks]]` to
the source sessions. If the answer is substantial, it'll ask whether to
save it under `wiki/syntheses/`.

## Step 5 — Review new candidates

When `/wiki-ingest` discovers a possibly-new entity, it doesn't write
directly to `wiki/entities/`. It drops the draft into
`wiki/candidates/entities/` with `status: candidate` so you can gate it:

```
/wiki-review
```

Claude Code will walk you through pending candidates and offer
`promote`, `merge`, or `discard`. Each action is non-destructive:
discarded candidates land under `wiki/archive/candidates/` with a
reason file.

Full workflow: **[`docs/reference/cache-tiers.md`](../reference/cache-tiers.md)** (lifecycle + staleness).

## Step 6 — Keep the wiki healthy

After a promote/merge, run:

```
/wiki-lint
```

It runs the 13 structural + LLM-powered lint rules. Output:

```
== 28 issues: 0 errors, 22 warnings, 6 info
  link_integrity (22)
  orphan_detection (6)
  stale_candidates (0)
  cache_tier_consistency (0)
```

Zero errors = wiki is valid. Warnings are fine as long as they're tracked.

---

## The minimum daily loop

```
Open Claude Code, work on something.
/wiki-sync            (after the session)
/wiki-review          (if it flagged candidates)
/wiki-query <q>       (when you need to recall)
```

That's it. Run `/wiki-lint` on demand when you want a health check.

---

## Verify

```bash
python3 -m llmwiki --version            # → llmwiki <version>
python3 -m llmwiki sync --dry-run       # shows what the next /wiki-sync would do
cat wiki/log.md | tail -20              # every operation is appended here
```

The log is grep-parseable:

```bash
grep "^## \[" wiki/log.md | tail -10
```

---

## Troubleshooting

**Slash commands don't appear in Claude Code** — you're not in the llm-wiki
working directory, or Claude Code was opened before `.claude/commands/`
existed. Restart Claude Code from inside the repo.

**`/wiki-sync` keeps re-processing old sessions** — the converter state file
got lost. Check `.llmwiki-state.json` at the repo root; if missing, pass
`--force` once and let it rebuild.

**`/wiki-query` returns "I couldn't find anything"** — the wiki is under
`wiki/sources/<project>/` by default; confirm `ls wiki/sources | wc -l`
returns > 0. If 0, the ingest step hasn't run yet.

---

## Next

→ **[04 · Use with Codex CLI](04-use-with-codex-cli.md)** — the same workflow, against Codex sessions.
