Feature: Keyboard navigation shortcuts
  As a visitor who prefers the keyboard
  I want `g h`, `g p`, `g s`, `?` and `/` to work everywhere
  So I never need to reach for the mouse

  Background:
    Given a built llmwiki site is served
    And I visit the homepage

  Scenario: "g h" jumps to home
    When I press "g" then "h"
    Then the URL path ends with "index.html" or "/"

  Scenario: "g p" jumps to projects
    When I press "g" then "p"
    Then the URL path contains "projects/index.html"

  Scenario: "g s" jumps to sessions
    When I press "g" then "s"
    Then the URL path contains "sessions/index.html"

  Scenario: "?" opens the help dialog
    When I press "?"
    Then the help dialog becomes visible
