Feature: Command palette
  As a visitor navigating with the keyboard
  I want the Cmd+K / Ctrl+K palette to open and filter instantly
  So I can jump between pages without clicking

  Background:
    Given a built llmwiki site is served

  Scenario: Cmd+K opens the palette and focuses the input
    When I visit the homepage
    And I press "Meta+K"
    Then the command palette becomes visible
    And the palette input is focused

  Scenario: Typing a query filters palette results
    When I visit the homepage
    And I press "Meta+K"
    And I type "python" into the palette input
    Then the palette results contain "e2e-python-demo"
