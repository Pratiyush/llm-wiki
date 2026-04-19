---
title: "04 · Use with Codex CLI"
type: tutorial
docs_shell: true
---

# 04 · Use with Codex CLI

**Time:** 10 minutes
**You'll need:** A working `llmwiki` CLI and Codex CLI installed with at least one session at `~/.codex/sessions/`.
**Result:** Codex CLI sessions ingested alongside your Claude Code ones, searchable from the same wiki.

---

## Why this matters

If you use Codex CLI alongside Claude Code, their session transcripts shouldn't
live in separate silos. llmwiki's adapter registry pulls from every AI agent
it recognises — your wiki becomes a unified view across agents.

---

## Step 1 — Verify the adapter picks up your sessions

```bash
python3 -m llmwiki adapters | grep codex_cli
```

Expected:

```
codex_cli         no        ✓            Codex CLI — reads ~/.codex/sessions/
```

`configured: ✓` means the adapter sees the session store. `default: no` means
it's off unless you opt in.

If `configured: -`, Codex CLI hasn't written sessions yet. Run `codex` once
and retry.

See **[`docs/adapters/codex-cli.md`](../adapters/codex-cli.md)** for the full adapter spec.

## Step 2 — Enable the adapter

Edit (or create) `sessions_config.json`:

```json
{
  "codex_cli": {
    "enabled": true
  }
}
```

Or pass it explicitly to `sync`:

```bash
python3 -m llmwiki sync --adapter claude_code codex_cli
```

## Step 3 — Sync

```bash
python3 -m llmwiki sync
```

Expected addition to the output:

```
==> codex_cli: 18 sessions
✓ wrote 18 pages under raw/sessions/
```

Codex sessions appear under `raw/sessions/<YYYY-MM-DDTHH-MM>-<project>-<slug>.md`
with `model: <codex-model>` in frontmatter so you can filter by agent later.

## Step 4 — Filter by agent in the site

Open the sessions index — each row carries an agent badge
(Claude / Codex / Copilot / Cursor / Gemini). The filter bar at the top
of the table lets you narrow by agent with a single click.

## Step 5 — Cross-agent queries

Because all sessions land in the same `wiki/` tree, `/wiki-query` doesn't
care which agent produced what. Ask:

```
/wiki-query which agent did I use for refactoring the lint rules?
```

and you'll get an answer spanning both Claude and Codex sessions, with
inline `[[wikilinks]]` back to the originals.

---

## The minimum daily loop

```
1. Work in Codex CLI.
2. llmwiki sync                      (or /wiki-sync from within Claude Code — it pulls both)
3. llmwiki query "..."               (CLI) or /wiki-query (from Claude Code)
```

---

## Verify

```bash
python3 -m llmwiki adapters | grep -E "claude_code|codex_cli"
grep -l 'model: codex' wiki/sources/**/*.md 2>/dev/null | wc -l   # ≥ 0 (0 is fine if no Codex sessions)
```

---

## Troubleshooting

**`codex_cli` still says `configured: -`** — your Codex version writes sessions somewhere non-standard. Check where via `ls ~/.codex/` and file an issue with the path so we can add detection.

**Sessions ingested but no agent badge shows** — the badge comes from the `model` frontmatter field; older Codex sessions may not set it. Re-ingest with `--force` to re-parse with the latest adapter.

**Mixed-agent query returns only one agent's sessions** — confirm `wiki/overview.md` references both. If not, re-run `/wiki-sync` so overview regenerates.

---

## Next

→ **[05 · Query your wiki](05-querying-your-wiki.md)** — master the slash commands that make the wiki worth having.
