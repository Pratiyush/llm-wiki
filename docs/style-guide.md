---
title: "Docs style guide"
type: navigation
docs_shell: true
---

# Docs style guide

**Who this is for:** anyone adding or editing documentation under `docs/`.

**What it enforces:** voice, structural consistency, and the specific
editorial patterns the tutorials use so everything reads like it was
written by one careful person.

---

## Voice

**Minimalism + trust & authority.** That's the whole brand.

| Do | Don't |
|---|---|
| "The adapter reads `~/.claude/projects/`." | "Our amazing adapter seamlessly integrates with Claude Code." |
| "Run `llmwiki sync`. It takes 5 s for the incremental case." | "Simply run `llmwiki sync` and watch the magic happen!" |
| "If X fails, it's a bug in the docs. File an issue." | "Need help? Don't hesitate to reach out!" |
| Give numbers. "647 sessions, 93 sub-agents, 5 s incremental." | Adjectives without numbers. "Fast, scalable, robust." |

Rules of thumb:

- **Evidence-first.** Show the command. Show the expected output. Show
  a number. Everything else is vapor.
- **No exclamation marks.** Ever.
- **No emoji in body copy.** Tables and headers get ✓ / ✗ where they
  genuinely save a word. No confetti, no ✨.
- **Second person, active voice.** "You'll see…" not "users will observe…".
- **Don't narrate your narration.** "In this tutorial we'll…" is a tax
  on the reader. Start with the work.

---

## Tutorial structure

Every file under `docs/tutorials/` follows the exact same skeleton:

```markdown
---
title: "NN · Short verb phrase"
type: tutorial
docs_shell: true
---

# NN · Short verb phrase

**Time:** <minutes>
**You'll need:** <prereqs>
**Result:** <one sentence — what the user has after finishing>

---

## Why this matters

<one or two paragraphs — no marketing, just why this step exists>

---

## Step 1 — <verb + object>

<commands, expected output, one paragraph of explanation>

## Step 2 — …

...

---

## Verify

<commands the user can run to prove it worked>

---

## Troubleshooting

**Error string** — one-sentence diagnosis + fix.
**Another error** — diagnosis + fix.

---

## Next

→ **[NN+1 · Next tutorial](NN+1-...md)** — one sentence on why they'd click.
```

Required sections, in order: header · Why · numbered Steps · Verify ·
Troubleshooting · Next. The doc-structure guardrail test enforces this.

---

## Callouts

Use blockquotes, **not** custom syntax. Three recognised prefixes:

```markdown
> **Trusted.** This is a safe read-only operation. Nothing is written.

> **Warning.** This overwrites files. Back up first or pass `--dry-run`.

> **Result.** Expected output after running the step.
```

The `.docs-shell` CSS renders them all with a thin purple left-rule and
a subtle tinted background. No icons, no colored banners.

---

## Code blocks

- **Shell commands** fence with `bash` and prefix with `$` **only** when
  the output follows on the next lines:
  ```bash
  $ llmwiki --version
  llmwiki 1.1.0rc2
  ```
  If it's just the command (no output in the same block), drop the `$`:
  ```bash
  llmwiki sync --dry-run
  ```
- **Python** fences with `python` (never `py`).
- **JSON / YAML / TOML** use their own language tag.

---

## Linking

- **Cross-links within docs/**: relative paths, always end in `.md`
  (`[text](reference/cache-tiers.md)` from `docs/index.md`, or
  `[text](../reference/cache-tiers.md)` from a tutorial). The static-site
  build rewrites to `.html`; the guardrail test checks every relative
  link resolves.
- **Anchor links**: kebab-case, matching the heading slug
  (e.g. `[text](reference/cache-tiers.md#the-four-tiers)` with the
  relative prefix that suits the source file).
- **External links**: use the canonical URL, no tracking params.
  Prefer the project's own repo (`https://github.com/Pratiyush/llm-wiki/issues/N`)
  over screenshots of issues.
- **Never link to `master`** when you could link to a tagged version.
  (`/v1.1.0-rc2/…` beats `/master/…`.)

---

## Adding a new tutorial

1. Pick the next number. Current last tutorial is `07`; a new one is `08-<slug>.md`.
2. Copy the skeleton above. Fill in header, Why, Steps, Verify, Troubleshooting, Next.
3. Add a row to the table in `docs/index.md` under the correct section.
4. Update the "Next" link on the previous tutorial to point to yours.
5. Add any new internal links the tutorial needs to existing pages.
6. Run the guardrail test: `python3 -m pytest tests/test_docs_structure.py`.
7. Build locally: `python3 -m llmwiki build && python3 -m llmwiki serve`.
8. Visually inspect the rendered page at `http://127.0.0.1:8765/docs/tutorials/<file>.html`.

---

## Adding a new reference page

Reference pages live under `docs/reference/`. They're looser than
tutorials (no required sections, no step numbering). Add a row to the
Reference table in `docs/index.md` and cross-link from whichever
tutorial introduces the feature.

---

## What never to do

- **Don't rewrite a tutorial's opening prose to "market" the feature.** The
  audience has already read the README. They're here to work.
- **Don't embed videos.** The docs must survive without JavaScript.
- **Don't add a TL;DR.** The `**Time / You'll need / Result**` block is
  the TL;DR.
- **Don't name a file `README.md` in `docs/`.** GitHub surfaces it over
  `index.md`, which breaks the hub.
- **Don't push without running the tests.** The guardrails exist because
  docs rot silently.

---

## Tests that protect the docs

`tests/test_docs_structure.py` enforces:

- Every tutorial has Header + Why + Steps + Verify + Troubleshooting + Next.
- Every link from `docs/index.md` resolves to a real file.
- Every tutorial's `title:` matches its filename (`NN · …`).
- No `<script>` or raw HTML in tutorial bodies.
- Docs-shell CSS is appended to the main stylesheet.

Run: `python3 -m pytest tests/test_docs_structure.py`.

If the test fails with a clear message, fix the content. If it fails
with an unclear message, fix the test too — it's docs-protecting docs.
