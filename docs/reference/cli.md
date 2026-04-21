---
title: "CLI reference"
type: navigation
docs_shell: true
---

# CLI reference

**Every** `python3 -m llmwiki <subcommand>` — with every flag, realistic
examples, and expected output. If a command isn't listed here it isn't
shipping. This page is generated against the live argparse tree, so
adding a flag without documenting it will fail the guardrail test.

Global flags: `-h` / `--help` on every command, `--version` at the root.

---

## Top-level

```bash
python3 -m llmwiki --version    # → llmwiki <version>
python3 -m llmwiki --help       # list every subcommand
python3 -m llmwiki              # same as --help
```

The shorter alias `llmwiki` works too once the package is installed
(`pip install llmwiki` or via Homebrew — see
[`deploy/pypi-publishing.md`](../deploy/pypi-publishing.md) /
[`deploy/homebrew-setup.md`](../deploy/homebrew-setup.md)).

---

## `init` — scaffold `raw/` / `wiki/` / `site/`

Creates the three data directories + seeds nine navigation files inside
`wiki/`.

```bash
python3 -m llmwiki init
```

**Flags:** none.

**Expected output:**

```
  raw/sessions/
  wiki/sources/
  wiki/entities/
  wiki/concepts/
  wiki/syntheses/
  site/
  seeded wiki/dashboard.md
  seeded wiki/index.md
  ...
```

**Idempotent.** Safe to re-run — it never overwrites files that exist.

---

## `sync` — convert `.jsonl` sessions to markdown

The workhorse. Walks every configured adapter, converts new sessions
into `raw/sessions/`, then (by default) auto-builds and auto-lints.

```bash
python3 -m llmwiki sync
python3 -m llmwiki sync --dry-run
python3 -m llmwiki sync --since 2026-04-01 --project llm-wiki
python3 -m llmwiki sync --adapter claude_code codex_cli
python3 -m llmwiki sync --no-auto-build --no-auto-lint
python3 -m llmwiki sync --vault "~/Documents/Obsidian Vault"
python3 -m llmwiki sync --vault ~/my-vault --allow-overwrite
python3 -m llmwiki sync --force
python3 -m llmwiki sync --download-images
```

### Flags

| Flag | What |
|---|---|
| `--adapter NAME [NAME ...]` | Limit to specific adapters. Default: every adapter with a session store on disk. |
| `--since YYYY-MM-DD` | Only sessions on/after this date (e.g. `--since 2026-04-01`). |
| `--project SUBSTRING` | Filter by project-slug substring. |
| `--include-current` | Include sessions < 60 min old (default skips live ones). |
| `--force` | Ignore the mtime state file, reconvert everything. |
| `--dry-run` | Print what would be written, touch nothing. |
| `--download-images` | Mirror remote image URLs into `raw/assets/`. |
| `--auto-build` / `--no-auto-build` | Rebuild `site/` after sync (default: on). |
| `--auto-lint` / `--no-auto-lint` | Run `lint` after sync (default: on). |
| `--vault PATH` | Vault-overlay mode — write new pages inside the given Obsidian / Logseq vault instead of `wiki/`. See [`guides/existing-vault.md`](../guides/existing-vault.md). |
| `--allow-overwrite` | With `--vault`: allow clobbering existing vault pages (default: refuse, append under `## Connections` instead). |

### Expected output (typical)

```
==> claude_code: 3 new sessions since last sync
✓ wrote 3 pages under raw/sessions/
✓ ingested into wiki/sources/ (2 new entities, 1 new concept)
✓ auto-build: site/ rebuilt (690 HTML files)
✓ auto-lint: 28 issues: 0 errors, 22 warnings, 6 info
```

### Common recipes

- Nightly cron-style sync of one project only:
  `llmwiki sync --project my-project --no-auto-lint --since $(date -v-1d +%Y-%m-%d)`
- Staging sweep before a release: `llmwiki sync --force --dry-run`
- Vault-overlay round-trip: `llmwiki sync --vault "~/Documents/Obsidian Vault"`

---

## `build` — compile the static HTML site

Turns `wiki/` markdown into `site/` HTML.

```bash
python3 -m llmwiki build
python3 -m llmwiki build --out ~/public_html
python3 -m llmwiki build --search-mode tree
python3 -m llmwiki build --synthesize --claude /usr/local/bin/claude
python3 -m llmwiki build --vault ~/my-vault --out ~/site
```

### Flags

| Flag | What |
|---|---|
| `--out PATH` | Output directory. Default: `./site/`. |
| `--synthesize` | Call the `claude` CLI for overview synthesis (experimental). |
| `--claude PATH` | Path to the `claude` binary. Default: `/usr/local/bin/claude`. |
| `--search-mode {auto,tree,flat}` | Search routing mode (#53). `auto` picks tree vs flat from heading depth; `tree` / `flat` force the mode. Default: `auto`. |
| `--vault PATH` | Vault-overlay mode — build from an existing Obsidian / Logseq vault. Output still lands at `--out`. |

### Expected output (final lines)

```
  wrote search-index.json (7 KB meta) + 30 chunks (904 KB total) · tree mode · 64% deep pages
  wrote 7 AI-consumable exports: ai-readme.md, graph.jsonld, llms-full.txt, llms.txt, robots.txt, rss.xml, sitemap.xml
  wrote site/graph.html (interactive graph viewer)
  wrote site/prototypes/index.html (6 prototype states)
  wrote site/docs/ (94 editorial pages: hub + tutorials + style guide)
==> build complete: 703 HTML files, 61 MB
```

---

## `serve` — start a local HTTP server

```bash
python3 -m llmwiki serve
python3 -m llmwiki serve --port 9000
python3 -m llmwiki serve --dir ~/public_html
python3 -m llmwiki serve --open
```

### Flags

| Flag | What |
|---|---|
| `--dir PATH` | Directory to serve. Default: `./site/`. |
| `--port N` | Port. Default: `8765`. |
| `--host ADDR` | Bind address. Default: `127.0.0.1`. Use `0.0.0.0` to share on LAN. |
| `--open` | Open the browser at the root URL after starting. |

**Stdlib only** — it's `http.server` underneath. Safe for local use;
don't expose to the public internet.

---

## `adapters` — list every adapter + its status

```bash
python3 -m llmwiki adapters
```

**Flags:** none.

**Expected output:**

```
Registered adapters:
  name              default   configured    description
  ----------------  --------  ------------  ----------------------------------------
  chatgpt           no        -             ChatGPT — parses conversations.json …
  claude_code       yes       ✓            Claude Code — reads ~/.claude/projects/
  codex_cli         no        ✓            Codex CLI — reads ~/.codex/sessions/
  copilot           no        -             GitHub Copilot — reads VS Code …
  cursor            no        -             Cursor — reads VS Code workspaceStorage
  gemini_cli        no        -             Gemini CLI — reads ~/.gemini/
  jira              no        -             Jira — reads via REST API
  meeting           no        -             Meeting transcripts (VTT/SRT)
  obsidian          no        -             Obsidian — reads a vault
  opencode          no        -             OpenCode / OpenClaw sessions
  pdf               no        -             PDF source files
  web_clipper       no        -             Obsidian Web Clipper intake
```

Columns: **default** (runs when you don't pass `--adapter`), **configured**
(adapter sees a valid session store on this machine).

---

## `graph` — build the knowledge graph

```bash
python3 -m llmwiki graph                     # both json + html
python3 -m llmwiki graph --format json
python3 -m llmwiki graph --format html
```

### Flags

| Flag | What |
|---|---|
| `--format {json,html,both}` | Output format(s). Default: `both`. |

Emits `graph/graph.json` (nodes + edges) and/or `graph/graph.html`
(vis-network interactive viewer). The interactive version is also
auto-copied into `site/graph.html` on every `build`.

---

## `quarantine` — inspect failed syncs

```bash
python3 -m llmwiki quarantine list
python3 -m llmwiki quarantine list --adapter claude_code
python3 -m llmwiki quarantine clear --all
python3 -m llmwiki quarantine clear /Users/you/.claude/projects/foo.jsonl
python3 -m llmwiki quarantine retry
```

### Flags (per-subcommand)

| Subcommand | Flag | What |
|---|---|---|
| `list` | `--adapter NAME` | Filter to one adapter |
| `clear` | `--all` | Wipe every entry |
| `clear` | `--adapter NAME` | Restrict the clear to one adapter |
| `retry` | `--adapter NAME` | Filter the retry plan |

`sync` automatically records every convert exception in
`.llmwiki-quarantine.json` so you can see *what didn't sync and why*
without re-tailing stderr. Clear a source after you've fixed the
underlying bug and the next `sync` retries it. G-14 · #300.

---

## `backlinks` — inject managed `## Referenced by` blocks

```bash
python3 -m llmwiki backlinks                               # real run
python3 -m llmwiki backlinks --dry-run                     # preview
python3 -m llmwiki backlinks --verbose                     # + top-20 most referenced
python3 -m llmwiki backlinks --max-entries 100             # custom cap
python3 -m llmwiki backlinks --prune                       # strip every block
```

### Flags

| Flag | What |
|---|---|
| `--wiki-dir PATH` | Override wiki root (default `./wiki/`) |
| `--max-entries N` | Max backlinks per page (default 50; truncation footer added) |
| `--dry-run` | Preview writes without touching disk |
| `--prune` | Remove every backlink block (inverse of default) |
| `--verbose` / `-v` | Print top-20 most-referenced pages after injection |

Walks `wiki/` and, for every page that another wiki page links to,
injects a managed `## Referenced by` section bounded by
`<!-- BACKLINKS:START --> … <!-- BACKLINKS:END -->` sentinels.
Rerun is idempotent — the block gets replaced, everything else on the
page stays intact. Entries are sorted newest-first when referrers
carry a `date:` field, alphabetical otherwise. Skips `archive/` and
`_context.md` stubs.

Fixes the orphan problem: before `backlinks`, 95% of wiki pages had no
inbound link visible on their own page. After, the graph becomes
navigable + Obsidian renders backlinks natively. #328.

---

## `references` — list every page linking to an entity

```bash
python3 -m llmwiki references RAG
python3 -m llmwiki references RAG --with-dated-claims
python3 -m llmwiki references AndrejKarpathy --wiki-dir other-wiki/
```

### Flags

| Flag | What |
|---|---|
| `--wiki-dir PATH` | Override wiki root (default `./wiki/`) |
| `--with-dated-claims` | Also print each referrer's dated claims about the target |

Reverse-reference index over the whole wiki. Output is one row per
referring page, sorted by source path for stable diffs. Pair with the
`stale_reference_detection` lint rule (rule #15) to surface *stale*
referrers — pages with dated claims about a target that's since been
updated. G-17 · #303.

---

## `tag` — curate the wiki tag-space

```bash
python3 -m llmwiki tag list                    # every tag + usage count
python3 -m llmwiki tag add claude-code sources/foo.md
python3 -m llmwiki tag rename obsidian Obsidian --dry-run
python3 -m llmwiki tag rename obsidian Obsidian         # do it
python3 -m llmwiki tag check --threshold 0.85
python3 -m llmwiki tag convention              # G-16 violations
```

### Subcommands

| Subcommand | What |
|---|---|
| `list` | Sort-by-count table of every tag in `wiki/` |
| `add <tag> <page>` | Append to a page's frontmatter (idempotent) |
| `rename <old> <new>` | Rewrite across every page; pair with `--dry-run` first |
| `check` | Near-duplicate detector (case-insensitive, SequenceMatcher) |
| `convention` | Flag projects using `tags:` / sources using `topics:` (G-16) |

### Flags (per subcommand)

| Subcommand | Flag | What |
|---|---|---|
| `list` / `check` / `convention` | `--wiki-dir <path>` | Override wiki root |
| `add` | `--field {tags,topics}` | Target frontmatter field (default `tags`) |
| `rename` | `--dry-run` | Preview without writing |
| `check` | `--threshold 0.0–1.0` | Similarity cutoff (default 0.85) |

G-15 · #301. Pairs with the `tags_topics_convention` lint rule
(G-16 · #302, rule #14) that fires on every `llmwiki lint` run.

---

## `log` — query `wiki/log.md` structurally

```bash
python3 -m llmwiki log                                       # last 10 of any op
python3 -m llmwiki log --since 2026-04-01
python3 -m llmwiki log --operation sync,synthesize
python3 -m llmwiki log --limit 50
python3 -m llmwiki log --format json
```

### Flags

| Flag | What |
|---|---|
| `--since YYYY-MM-DD` | Keep entries on or after this date |
| `--operation <csv>` | Comma-separated ops to keep: `sync`, `synthesize`, `lint`, `ingest`, `query`, `build` |
| `--limit N` | Max rows to print (default 10; `0` = unlimited) |
| `--format {text,json}` | `text` for humans, `json` for scripts |

`wiki/log.md` is the append-only history of every pipeline operation.
This command parses it into structured events so you can find
"everything that synced on 2026-04-19" without eyeballing the file.
Pairs with `llmwiki sync --status` for the live-counters view.
G-13 · #299.

---

## `sync --status` — observability report

```bash
python3 -m llmwiki sync --status
python3 -m llmwiki sync --status --recent 5
```

Non-destructive reporter. Prints:

1. Last-sync timestamp (from `.llmwiki-state.json` `_meta`).
2. Per-adapter counters: `discovered / converted / unchanged / live /
   filtered / errored` (written by the previous `sync` run).
3. Orphan state entries (keys pointing at files that no longer exist).
4. Quarantined sources (see `quarantine`).
5. Optional `--recent N`: last N sync/synthesize entries from `log.md`.

G-03 · #289. Does **not** run a sync — use `llmwiki sync` for that.

---

## `watch` — long-running session-store watcher

```bash
python3 -m llmwiki watch
python3 -m llmwiki watch --interval 30 --debounce 5
python3 -m llmwiki watch --adapter claude_code --dry-run
```

### Flags

| Flag | What |
|---|---|
| `--adapter NAME [NAME ...]` | Limit to named adapters. |
| `--interval SECONDS` | Polling interval. Default: 10. |
| `--debounce SECONDS` | Wait this long after a change before syncing. Default: 2. |
| `--dry-run` | Detect changes, don't sync. |

Use this when you want hands-off ingestion during a long coding session.
Foreground process — Ctrl+C to stop.

---

## `export-obsidian` — mirror `wiki/` into a vault

```bash
python3 -m llmwiki export-obsidian --vault ~/MyVault
python3 -m llmwiki export-obsidian --vault ~/MyVault --subfolder "LLM Wiki"
python3 -m llmwiki export-obsidian --vault ~/MyVault --clean --dry-run
```

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | Obsidian vault root. **Required.** |
| `--subfolder NAME` | Subfolder inside the vault. Default: `llm-wiki`. |
| `--clean` | Delete the target subfolder before copying. |
| `--dry-run` | Print what would be copied, touch nothing. |

Contrast with `link-obsidian` (which symlinks the project into the vault)
and `sync --vault` (which writes directly into the vault).

---

## `export-marp` — generate a Marp slide deck

```bash
python3 -m llmwiki export-marp --topic "cache tiers"
python3 -m llmwiki export-marp --topic Karpathy --out ~/slides/karpathy.marp.md
```

### Flags

| Flag | What |
|---|---|
| `--topic STRING` | Search term. **Required.** |
| `--out PATH` | Output path. Default: `wiki/exports/<topic>.marp.md`. |
| `--wiki PATH` | Wiki dir. Default: `./wiki`. |

---

## `export-qmd` — export as Quarto collection

```bash
python3 -m llmwiki export-qmd --out ~/quarto/llmwiki
python3 -m llmwiki export-qmd --source-wiki ~/other-wiki --collection myproject
```

### Flags

| Flag | What |
|---|---|
| `--out PATH` | Output directory. **Required.** |
| `--source-wiki PATH` | Source wiki dir. Default: `./wiki`. |
| `--collection NAME` | Name written into `qmd.yaml`. Default: `llmwiki`. |

---

## `check-links` — verify every internal link in `site/`

```bash
python3 -m llmwiki check-links
python3 -m llmwiki check-links --fail-on-broken
python3 -m llmwiki check-links --limit 100
```

### Flags

| Flag | What |
|---|---|
| `--site-dir PATH` | Site dir. Default: `./site`. |
| `--fail-on-broken` | Exit 1 if any broken links found. |
| `--limit N` | Max links to verify. |

Unlike the `lint` command (which checks wikilinks in source), this walks
compiled `site/*.html` and verifies every `<a href>` resolves.

---

## `export` — AI-consumable site exports

Single positional argument picks the format.

```bash
python3 -m llmwiki export llms-txt
python3 -m llmwiki export llms-full-txt
python3 -m llmwiki export jsonld
python3 -m llmwiki export sitemap
python3 -m llmwiki export rss
python3 -m llmwiki export robots
python3 -m llmwiki export ai-readme
python3 -m llmwiki export all --out ~/custom-site
```

### Positional

| Value | Writes |
|---|---|
| `llms-txt` | `site/llms.txt` — llmstxt.org spec |
| `llms-full-txt` | `site/llms-full.txt` — flattened plain-text corpus (≤ 5 MB) |
| `jsonld` | `site/graph.jsonld` — schema.org entity graph |
| `sitemap` | `site/sitemap.xml` |
| `rss` | `site/rss.xml` |
| `robots` | `site/robots.txt` |
| `ai-readme` | `site/ai-readme.md` |
| `all` | all of the above |

### Flags

| Flag | What |
|---|---|
| `--out PATH` | Output directory. Default: `./site/`. |

---

## `manifest` — build + validate perf manifest

```bash
python3 -m llmwiki manifest
python3 -m llmwiki manifest --fail-on-violations
```

### Flags

| Flag | What |
|---|---|
| `--site-dir PATH` | Site dir. Default: `./site`. |
| `--fail-on-violations` | Exit 1 if any perf-budget violations. |

Writes `site/manifest.json` with SHA-256 hashes for every file + a
perf-budget check (cold build < 30 s, per-page < 3 MB, `llms-full.txt`
< 10 MB, etc).

---

## `lint` — run 13 wiki-quality rules

```bash
python3 -m llmwiki lint
python3 -m llmwiki lint --json
python3 -m llmwiki lint --fail-on-errors
python3 -m llmwiki lint --rules link_integrity,orphan_detection
python3 -m llmwiki lint --include-llm
python3 -m llmwiki lint --wiki-dir ~/another-wiki
```

### Flags

| Flag | What |
|---|---|
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--rules NAMES` | Comma-separated rule names. Default: all applicable. |
| `--include-llm` | Also run the three LLM-powered rules (requires a callback wired in). |
| `--json` | JSON output. |
| `--fail-on-errors` | Exit 1 if any error-severity issues. |

### Rules

8 structural (`frontmatter_completeness`, `frontmatter_validity`,
`link_integrity`, `orphan_detection`, `content_freshness`,
`entity_consistency`, `duplicate_detection`, `index_sync`) + 3 LLM-powered
(`contradiction_detection`, `claim_verification`, `summary_accuracy`) +
2 v1.1+ (`stale_candidates`, `cache_tier_consistency`).

### Expected output

```
  scanned 31 pages
  28 issues: 0 errors, 22 warnings, 6 info

## link_integrity (22)
  [warning] entities/GPT5.md: broken wikilink [[MultimodalModels]]
  ...
```

---

## `install-skills` — mirror `.claude/skills/` into sibling agent paths

```bash
python3 -m llmwiki install-skills
```

**Flags:** none.

Creates symlinks under `.codex/skills/` + `.agents/skills/` so Codex CLI,
Gemini CLI, Cursor, etc. see the same skills Claude Code does.

---

## `candidates` — approval workflow

Positional `action` picks `list` / `promote` / `merge` / `discard`.

```bash
python3 -m llmwiki candidates list
python3 -m llmwiki candidates list --stale --stale-days 60
python3 -m llmwiki candidates list --json
python3 -m llmwiki candidates promote --slug NewEntity
python3 -m llmwiki candidates promote --slug NewEntity --kind concepts
python3 -m llmwiki candidates merge --slug DuplicateFoo --into Foo
python3 -m llmwiki candidates discard --slug BogusEntity --reason "LLM hallucinated"
```

### Flags

| Flag | What |
|---|---|
| `--slug NAME` | Candidate slug. **Required** for `promote` / `merge` / `discard`. |
| `--into NAME` | For `merge`: target slug. |
| `--reason TEXT` | For `discard`: why (written to archive's `.reason.txt`). |
| `--kind {entities,concepts,sources,syntheses}` | Subtree. Auto-detected if omitted. |
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--stale` | With `list`: only stale candidates. |
| `--stale-days N` | Staleness threshold. Default: 30. |
| `--json` | JSON output for `list`. |

See [`guides/existing-vault.md`](../guides/existing-vault.md) for the
round-trip semantics when a candidate lives inside a vault.

---

## `synthesize` — LLM-backed source-page synthesis

```bash
python3 -m llmwiki synthesize --check            # probe the backend
python3 -m llmwiki synthesize --estimate         # cost preview, no API calls
python3 -m llmwiki synthesize --dry-run          # list what would be synth'd
python3 -m llmwiki synthesize --force            # re-synth everything
python3 -m llmwiki synthesize                    # real run
```

### Flags

| Flag | What |
|---|---|
| `--check` | Probe backend availability + exit (0 if reachable). |
| `--dry-run` | List sessions that would be synthesized, write nothing. |
| `--force` | Ignore state, re-synth every source. |
| `--estimate` | Print cached-vs-fresh token + dollar estimate (#50). |

Backend is picked from `synthesis.backend` in `sessions_config.json`
(`dummy` by default, `ollama` for local, future `anthropic`). See
[`reference/prompt-caching.md`](prompt-caching.md).

### Auto-tagging (#351)

Every `synthesize` call now produces **topical** tags alongside the
deterministic baseline.  The synthesizer emits a
`<!-- suggested-tags: prompt-caching, rag, github-actions -->` block
as the first line of its response; the pipeline parses it, strips it
from the body, and merges the tags into frontmatter with:

- **Baseline preserved** — adapter, project slug, model family stay.
- **Maintainer wins** — on `--force`, whatever you added via
  `llmwiki tag add` is kept at the front of the list.
- **Stop-word filter** — the LLM can't re-add boilerplate tags
  (`session`, `summary`, `claude-code`, etc.).
- **Cap 5** — max 5 AI tags per page to prevent drift.
- **Near-dup rejection** — `prompt-cache` is blocked when
  `prompt-caching` is already on the page (threshold 0.80 + prefix
  check).

No extra API round-trip — rides the existing synthesis call, so cost
estimates from `--estimate` are unchanged.  If the backend returns no
suggested-tags block (dummy backend, malformed output), the page still
ships with baseline tags.

---

## `completion` — shell completion script

```bash
python3 -m llmwiki completion bash > ~/.bash_completion.d/llmwiki
python3 -m llmwiki completion zsh  > ~/.zsh/completions/_llmwiki
python3 -m llmwiki completion fish > ~/.config/fish/completions/llmwiki.fish
```

Positional: `bash` / `zsh` / `fish`. No flags. Stdlib-only (no
`argcomplete` dep).

---

## `link-obsidian` — symlink project into a vault

```bash
python3 -m llmwiki link-obsidian --vault "~/Documents/Obsidian Vault"
python3 -m llmwiki link-obsidian --vault ~/vault --name "My LLM Wiki"
python3 -m llmwiki link-obsidian --vault ~/vault --force
```

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | Obsidian vault root. **Required.** |
| `--name NAME` | Symlink name inside the vault. Default: `LLM Wiki`. |
| `--force` | Overwrite an existing symlink. |

Symlink-only — your Obsidian graph view / backlinks / full-text search
immediately see the wiki. Compare with `export-obsidian` (copy) and
`sync --vault` (in-place write).

---

## `version` — print the installed version

```bash
python3 -m llmwiki version
python3 -m llmwiki --version
```

Both print `llmwiki <version>`.

---

## Exit codes (conventions)

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Operation failed (user-visible error) |
| `2` | Usage error (bad flags, missing file, etc.) |

Subcommands document their own non-zero exit conditions where relevant
(`eval --fail-below`, `lint --fail-on-errors`,
`check-links --fail-on-broken`, `manifest --fail-on-violations`).

---

## Related

- **[Slash commands](slash-commands.md)** — the `/wiki-*` surface used from Claude Code.
- **[UI reference](ui.md)** — every screen + nav surface on the compiled site.
- **[Configuration](../configuration.md)** · **[Full configuration reference](../configuration-reference.md)**.
