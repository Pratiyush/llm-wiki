# Page-type specs (Planner output)

These markdown files are the **Planner pass** for the Playwright Test
Agents epic (#462, ADR-001). Each spec captures the expected behavior
of one page type (or one cross-cutting concern) on the built llmwiki
site, in a format the Generator agent can consume.

While the agents bootstrap (#464) is still gated on Node-install
approval in this repo, these specs are also useful as **documentation**:
they're the ground truth a reviewer can check a UI PR against, and
they map directly to scenarios in `tests/e2e/features/`.

## Spec inventory

| Spec | Page type | URL on the demo site |
|---|---|---|
| [home.md](home.md) | Home / index | `/` |
| [projects-index.md](projects-index.md) | Projects index | `/projects/` |
| [project-detail.md](project-detail.md) | Single project | `/projects/<slug>.html` |
| [sessions-index.md](sessions-index.md) | Sessions index (filter bar) | `/sessions/` |
| [session-detail.md](session-detail.md) | Single session | `/sessions/<project>/<slug>.html` |
| [docs-hub.md](docs-hub.md) | Docs landing | `/docs/` |
| [docs-page.md](docs-page.md) | Doc sub-page | `/docs/getting-started.html` |
| [graph.md](graph.md) | Knowledge graph | `/graph.html` |
| [theme-toggle.md](theme-toggle.md) | Cross-cutting: dark/light/system tri-state |

## How to use

- **Reviewers:** when reviewing a UI PR, scan the relevant spec and
  confirm the PR doesn't violate any "Must" line.
- **Generator agent (post-#464):** point it at one of these files and
  ask for a `tests/agents/<page>.spec.ts` that asserts every "Must".
- **Manual scenario authoring:** translate "Must" lines directly into
  Gherkin steps in `tests/e2e/features/`. The
  `tests/e2e/features/regression.feature` already follows this pattern
  for UI bugs #452–#460.

## Format convention

Every spec follows this structure:

```markdown
# <page-type> spec

## Goal
One sentence: why this page exists.

## URL pattern
The path(s) that resolve to this page type.

## Must
- Bullet list of invariants that MUST hold. These become test
  assertions. Phrase each as a single observable property.

## Should
- Bullet list of soft expectations. Reviewer-judgment, not a
  hard fail.

## Won't
- Anti-patterns or things explicitly NOT in scope.

## Cross-references
- Existing test scenarios that already cover parts of this spec
- Related issues / ADRs
```
