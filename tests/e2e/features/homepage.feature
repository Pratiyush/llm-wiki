Feature: Homepage
  As a visitor landing on the root of a built llmwiki
  I want the page to render the hero, the nav, and the projects grid
  So I can immediately see what the wiki contains

  Background:
    Given a built llmwiki site is served

  Scenario: Homepage hero is visible
    When I visit the homepage
    Then I see the page title contains "LLM Wiki"
    And I see a hero heading with text "LLM Wiki"
    And I see the subtitle mentions "sessions"

  Scenario: Nav bar has the main sections
    When I visit the homepage
    Then the nav bar has a "Home" link
    And the nav bar has a "Projects" link
    And the nav bar has a "Sessions" link

  Scenario: Projects grid lists the seeded demo projects
    When I visit the homepage
    Then I see a project card for "e2e-demo"
    And I see a project card for "e2e-demo-rust"
