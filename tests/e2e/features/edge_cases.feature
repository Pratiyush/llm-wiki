Feature: Edge cases that break first in production
  As a maintainer who's been burned by every one of these
  I want regression coverage for the weird-content scenarios
  So no future PR reintroduces a UX regression

  Background:
    Given a built llmwiki site is served

  Scenario: Empty-query palette still renders the initial result set
    When I visit the homepage
    And I press "Meta+K"
    And I clear the palette input
    Then the palette results area is visible
    And the palette results contain "e2e"

  Scenario: Fast typing into the palette does not crash the filter
    When I visit the homepage
    And I press "Meta+K"
    And I rapidly type "python rust ml api" into the palette input
    Then the palette results area is visible
    And the browser console has no errors

  Scenario: Escape key closes the command palette
    When I visit the homepage
    And I press "Meta+K"
    And the command palette becomes visible
    And I press "Escape"
    Then the command palette is hidden

  Scenario: 404 page does not exist and broken internal links return a real 404
    When I visit the path "/this-page-does-not-exist.html"
    Then the response status is 404

  Scenario: Raw HTML tags inside session prose do not leak into the DOM
    When I open the session "e2e-demo/2026-04-09-e2e-python-demo"
    Then the body innerHTML does not contain the string "<textarea class=\"md-source\" hidden>"
    And exactly 1 "textarea" element exists in the body

  Scenario: Print stylesheet hides the nav and the footer
    When I open the session "e2e-demo/2026-04-09-e2e-python-demo"
    And I emulate the "print" media type
    Then the nav bar is hidden
    And the mobile bottom nav is hidden

  Scenario: Browser console stays clean across home and session pages
    When I visit the homepage
    And I open the session "e2e-demo/2026-04-09-e2e-python-demo"
    Then the browser console has no errors
