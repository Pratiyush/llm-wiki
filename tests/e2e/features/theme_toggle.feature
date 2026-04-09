Feature: Theme toggle + highlight.js sync
  As a visitor reading code at night
  I want the theme toggle to flip everything to dark, including
    the syntax highlighter
  So the contrast stops burning my retinas

  Background:
    Given a built llmwiki site is served

  Scenario: Desktop theme toggle flips the data-theme attribute
    When I visit the homepage
    And I click the desktop "#theme-toggle" button
    Then the document root has data-theme "dark"

  Scenario: hljs theme stylesheet swap follows the toggle
    When I open the session "e2e-demo/2026-04-09-e2e-python-demo"
    And I click the desktop "#theme-toggle" button
    Then the "#hljs-light" stylesheet is disabled
    And the "#hljs-dark" stylesheet is enabled
