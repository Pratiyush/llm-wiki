# Security Policy

llmwiki processes session transcripts that often contain API keys,
passwords, tokens, file paths, and other sensitive information. Its
redaction layer and the surrounding privacy guarantees are the single
most important thing about the project.

If you find a vulnerability that affects any of the following, **please
report it privately** before filing a public issue:

- **Redaction bypass** — input that contains sensitive data but ends up
  in `raw/sessions/` unredacted
- **Data exfiltration** — any code path that reads a user's files
  outside the expected wiki/raw/site tree, or sends data over the network
- **XSS in the built site** — HTML injection via session content that
  survives `md_to_html()` and runs in a reader's browser (#74 was one of
  these — raw `<textarea>` leakage from assistant prose)
- **Path traversal** — file writes outside the output directory via
  crafted frontmatter fields or slugs
- **Supply-chain** — dependency CVEs in `markdown` (or anything else
  llmwiki calls into)

## Scope

In scope:

- `llmwiki/` — every Python module
- `.github/workflows/` — CI workflows that run on user PRs
- `site/` — generated HTML served to users
- `.claude/commands/`, `.claude/skills/`, `.claude/plugins/` — anything
  shipped to agents with elevated trust

Out of scope:

- Bugs in user wiki content (e.g. a user wrote a script tag into their
  own wiki page and now it runs — that's on the user)
- Denial of service via absurdly large `.jsonl` files (known limitation;
  mitigation is file-size caps in the converter)
- Security of third-party tools this project integrates with (`qmd`,
  `highlight.js`, Claude Desktop, etc.) — report those upstream

## How to report

Email the maintainer directly: `pratiyush1 [at] gmail [dot] com`

Include:

1. **What** — a one-line description of the vulnerability
2. **Where** — file path + line number if possible
3. **Repro** — minimal input that triggers the bug (redact any real
   session data before sending)
4. **Impact** — what an attacker could do
5. **Fix suggestion** — optional, but appreciated

## Response expectations

- **Acknowledgement**: within 3 days
- **Assessment**: within 7 days (is it in scope, what's the severity)
- **Fix**: for high-severity issues, targeted within 14 days
- **Disclosure**: coordinated public disclosure once a fix is merged and
  released. Reporters are credited in `CHANGELOG.md` unless they ask
  to stay anonymous.

## Privacy-first architecture

llmwiki is built around privacy. Before reporting, it helps to know
what's already in place:

- **Redaction is on by default** — username, API keys, tokens,
  passwords, and emails are regex-redacted before anything hits
  `raw/sessions/`
- **No telemetry, ever** — the tool never calls home
- **Localhost-only binding** — the built-in server binds to `127.0.0.1`
  unless the user explicitly passes `--host 0.0.0.0`
- **No runtime deps beyond stdlib + `markdown`** — smallest possible
  attack surface
- **`raw/` is gitignored** — contributors physically can't commit real
  session data (CI also greps for the maintainer's real username)
- **Privacy grep in CI** — `grep -r "<real_username>" .` must return
  zero hits in committed files
- **HTML-escape raw tags in prose** — fixed in #74; session content
  that mentions things like `<textarea>` can't leak into the DOM

Report anything that undermines these guarantees as a security issue,
not a regular bug.
