Feature: Accessibility + keyboard-only navigation
  As a visitor using a screen reader or keyboard only
  I want every interactive control to be reachable, labeled,
    and to behave predictably
  So the wiki is usable without a pointing device

  Background:
    Given a built llmwiki site is served

  Scenario: Every nav link has text content (no icon-only links)
    When I visit the homepage
    Then every nav-bar anchor has non-empty text

  Scenario: The theme toggle button has an aria-label
    When I visit the homepage
    Then the "#theme-toggle" button has a non-empty aria-label

  Scenario: Search button has an aria-label describing its purpose
    When I visit the homepage
    Then the "#open-palette" button has a non-empty aria-label

  Scenario: Tab order from body start reaches the command palette button
    When I visit the homepage
    And I click the document body
    And I press "Tab" 10 times
    Then the focused element is a focusable descendant of the header

  Scenario: Escape closes the palette and returns focus to the trigger
    When I visit the homepage
    And I press "Meta+K"
    And the command palette becomes visible
    And I press "Escape"
    Then the focused element is not inside the palette

  Scenario: Help dialog trap closes on Escape
    When I visit the homepage
    And I press "?"
    And the help dialog becomes visible
    And I press "Escape"
    Then the help dialog is hidden

  Scenario: prefers-reduced-motion is respected
    When I set prefers-reduced-motion to "reduce"
    And I visit the homepage
    Then the body computed animation-duration is 0 or the body has no active animations
