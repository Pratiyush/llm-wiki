Feature: Regression locks for UI bugs #452–#460
  As a maintainer
  I want a single Gherkin file that asserts each closed UI bug stays closed
  So that any regression in the same surface fails CI immediately

  # All 9 bugs in this file are CLOSED on master. Each scenario describes
  # the exact invariant the bug violated. The value is the regression
  # lock — if a future PR re-introduces the bug, the matching scenario
  # fails.
  #
  # STATUS: this file is the Generator-pass deliverable for #466. The
  # step definitions for several of these scenarios don't exist yet
  # (pending #467 — Generator pass via Playwright Test Agents, which
  # is gated on Node-install OK and the #464 bootstrap). To avoid
  # failing pytest-bdd discovery in the meantime, no `test_*.py` wrapper
  # imports `scenarios("features/regression.feature")` yet — the file
  # is documentation-quality until the step defs land.
  #
  # See specs/<page>.md for the full behavioural contract each bug
  # touches; the scenarios below assert just the specific invariant the
  # bug violated, not the full page spec. (#466 / parent #462)

  Background:
    Given a built llmwiki site is served

  # ─── #452 — sessions table column layout ─────────────────────────────
  Scenario: Sessions table Session column shows a unique id, not a duplicated date
    When I visit "/sessions/index.html"
    Then the Session column does not equal the Date column on any row
    And the Session column matches a short slug pattern, not a date

  # ─── #453 — activity timeline label semantics ────────────────────────
  Scenario: Sessions activity timeline label reports calendar span, not active-day count
    When I visit "/sessions/index.html"
    Then the timeline label contains the word "days"
    And the timeline label numeric prefix matches calendar span, not active-day count

  # ─── #454 — filter-by-slug input has a label ─────────────────────────
  Scenario: Filter-by-slug input is properly labeled for screen readers
    When I visit "/sessions/index.html"
    Then "#filter-text" has an associated label or aria-label
    And the label text is non-empty

  # ─── #455 — home cards have a date range ─────────────────────────────
  Scenario: Project cards show first / last session date range
    When I visit the homepage
    Then each ".card.card-project" contains a date range chip
    And the chip text matches a "DATE → DATE" or "N days ago" pattern

  # ─── #456 — graph page has the site nav ──────────────────────────────
  Scenario: Knowledge graph page renders with site nav, not standalone
    When I visit "/graph.html"
    Then the site nav bar is visible
    And the nav has links for Home, Projects, Sessions, Graph, Docs, Changelog
    And the "Graph" nav link carries class "active"

  # ─── #457 — docs hub version + sidebar ───────────────────────────────
  Scenario: Docs hub version line matches package version
    When I visit "/docs/index.html"
    Then the page contains the substring "v" + the current llmwiki version
    And the version line is NOT the literal string "v1.2.0" (regression of #457)

  # ─── #458 — theme persists across /docs/ navigation ──────────────────
  Scenario: Theme survives navigation from / to /docs/
    Given I have set the theme to "dark"
    When I visit the homepage
    And I navigate to "/docs/index.html"
    Then the html element has data-theme attribute equal to "dark"
    And the page is rendered using the dark palette

  # ─── #459 — WCAG contrast in both themes ─────────────────────────────
  Scenario: WCAG AA contrast holds for body text in dark mode
    Given I have set the theme to "dark"
    When I visit the homepage
    Then the computed contrast ratio between body text and background is at least 4.5

  Scenario: WCAG AA contrast holds for body text in light mode
    Given I have set the theme to "light"
    When I visit the homepage
    Then the computed contrast ratio between body text and background is at least 4.5

  # ─── #460 — mobile nav reaches every menu item ───────────────────────
  Scenario: All top-nav items are reachable on a mobile viewport via the hamburger
    Given I am on a 375px-wide mobile viewport
    When I visit the homepage
    And I open the nav hamburger
    Then I can see a link for "Home"
    And I can see a link for "Projects"
    And I can see a link for "Sessions"
    And I can see a link for "Graph"
    And I can see a link for "Docs"
    And I can see a link for "Changelog"
