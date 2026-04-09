Feature: Session detail page
  As a visitor drilling into a specific session
  I want the hero, the breadcrumbs, the conversation, and the
    navigation affordances to all render
  So I can read the transcript and find my way back

  Background:
    Given a built llmwiki site is served

  Scenario: Session page loads with the expected sections
    When I open the session "e2e-demo/2026-04-09-e2e-python-demo"
    Then the page title contains "e2e-python-demo"
    And I see a breadcrumbs bar
    And I see a "Copy as markdown" button
    And the article contains the heading "Summary"
    And the article contains a fenced code block with language "python"

  Scenario: Fenced code blocks are highlighted by hljs
    When I open the session "e2e-demo/2026-04-09-e2e-python-demo"
    Then at least one "pre > code.hljs" element becomes visible within 5 seconds
