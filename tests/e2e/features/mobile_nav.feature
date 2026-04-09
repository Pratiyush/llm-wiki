Feature: Mobile bottom nav
  As a visitor on a phone-sized viewport
  I want the bottom nav bar to appear
  And its Search + Theme buttons to actually work
  So the wiki is usable with one thumb

  Background:
    Given a built llmwiki site is served

  Scenario: Mobile bottom nav is visible on a small viewport
    When I visit the homepage on a mobile viewport
    Then the mobile bottom nav is visible
    And the mobile bottom nav has a "Search" button
    And the mobile bottom nav has a "Theme" button

  Scenario: Mobile Search button opens the palette
    When I visit the homepage on a mobile viewport
    And I tap the mobile bottom nav "Search" button
    Then the command palette becomes visible

  Scenario: Mobile Theme button toggles dark mode
    When I visit the homepage on a mobile viewport
    And I tap the mobile bottom nav "Theme" button
    Then the document root has data-theme "dark"
