# ADR-001 — Keep Python Playwright stack; add TS Test Agents alongside

**Date:** 2026-04-27
**Status:** Accepted
**Closes:** #463 (parent epic: #462)

## Context

Today the project's E2E suite runs entirely in Python:

- `pytest-playwright` drives a real browser
- `pytest-bdd` reads `tests/e2e/features/*.feature` files (Gherkin)
- `pytest-html` produces a browseable HTML report per run
- The `[e2e]` extra in `pyproject.toml` pulls in all three plus Pillow

This is wired into CI (`.github/workflows/e2e.yml`) and produces the
artifacts the team has been relying on (HTML report, screenshots,
Playwright traces). Total Python E2E test count today: 60+ scenarios
across responsive breakpoints, edge cases, accessibility, and visual
regression.

Playwright now ships a **Test Agents** trio (Planner / Generator /
Healer) bootstrapped via `npx playwright init-agents --loop=claude`.
The bootstrap writes:

- `playwright.config.ts`
- `tests/seed.spec.ts`
- `.github/` agent definitions consumed by `@playwright/test`
- `package.json` with the Node Playwright runner

The agents only target the **TypeScript / Node** Playwright runner.
There is no equivalent for `pytest-playwright`.

## Three paths considered

### A — Add TS Playwright **alongside** existing pytest stack ✓ chosen

Keep `tests/e2e/` Python suite. Land the TS bootstrap under
`tests-ts/` (or `tests/agents/`). Two CI jobs, two installs (Python +
Node), two reports.

- **Pro:** zero migration risk, the existing 60+ Python scenarios
  remain the contract, the agents-driven coverage is additive
- **Pro:** if the agents workflow proves valuable, the path to full
  migration (B) stays open; if it doesn't, the fallback (C) is free
- **Con:** dual maintenance burden, two stacks for newcomers to learn,
  two CI jobs

### B — Migrate to TS Playwright entirely

Port all `tests/e2e/` pytest-bdd scenarios to `@playwright/test`
syntax. Drop the Python `[e2e]` extra. One stack, one CI job, native
agents support.

- **Pro:** clean slate, agents-first, smaller maintenance surface
- **Con:** translation effort (60+ scenarios × Gherkin → TS DSL),
  project becomes Python+Node instead of pure-Python
- **Con:** the visual-regression coverage uses Pillow image-diff
  internally, which would need to be re-implemented in TS
- **Con:** during the porting window the Python suite still gates
  every PR — there's no point at which we're "done migrating" until
  the Python suite is removed, and removing it before TS is fully at
  parity creates a coverage hole

### C — Stay pure-Python, skip the agents workflow

Keep `pytest-playwright`. Don't adopt the Planner / Generator /
Healer trio. Continue authoring scenarios manually.

- **Pro:** simplest stack, no Node dependency
- **Con:** no agent-driven test generation. Each new UI bug needs a
  hand-written test. Drift detection stays manual.

## Decision: A

Path A is the lowest-risk way to evaluate Test Agents without
disrupting the contract that's already shipped. After one full epic
cycle (i.e. after #467 healer-in-CI has run for a release or two) we
can re-evaluate whether B is worth the porting effort.

## Constraints

- The TS bootstrap (#464) requires `npm install` and `npx playwright
  install`. In sandboxed development environments where Node installs
  are denied (e.g. `claude code` running in a constrained container),
  #464 must be deferred until the operator approves the install.
- Even with Path A, **most of the value of #465 and #466 can be
  captured manually** without the agents bootstrap:
  - #465 deliverable: `specs/*.md` plans for each page type. These
    are documentation; the Generator consumes them but they're useful
    even without it.
  - #466 deliverable: Gherkin scenarios under
    `tests/e2e/features/regression/` for each of UI bugs #452–#460.
    Each scenario fails before the fix and passes after.
- #467 (healer-in-CI auto-patch comments) genuinely requires #464 to
  ship — there is no Python equivalent.

## Layout (when #464 lands)

```
llm-wiki/
├── tests/
│   ├── e2e/                    # existing Python suite (kept)
│   │   ├── features/*.feature  # pytest-bdd Gherkin
│   │   ├── steps/*.py
│   │   └── conftest.py
│   └── agents/                 # NEW — TS Playwright Test Agents
│       ├── seed.spec.ts
│       └── *.spec.ts (generated)
├── specs/                      # NEW — page-type spec markdown
│   ├── home.md
│   ├── projects-index.md
│   ├── ...
├── playwright.config.ts        # NEW — TS runner config
├── package.json                # NEW — Node deps
└── pyproject.toml              # unchanged — Python deps
```

CI:

- `e2e.yml` — existing Python E2E job (unchanged)
- `agents-e2e.yml` — NEW job running `npx playwright test`,
  uploading HTML report + traces

## Out of scope for this ADR

- Whether to drop the Python suite later (Path B). Re-evaluate after
  #467 ships and we have one release of healer-in-CI experience.
- Whether to share fixtures between the two suites. They both build
  the demo site and serve it on a free port; could be factored later.
- Browser matrix. Both suites run chromium today; whether to add
  firefox / webkit to the agents suite is a #464 question.

## References

- https://playwright.dev/docs/test-agents
- #462 — Epic: Adopt Playwright Test Agents site-wide
- #464 — Bootstrap: `npx playwright init-agents`
- The existing Python E2E config: `pyproject.toml` `[project.optional-dependencies].e2e`
