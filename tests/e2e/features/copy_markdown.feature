Feature: Copy-as-markdown button
  As a visitor wanting to paste a session into an LLM chat
  I want one click to copy the raw markdown to my clipboard
  So I don't have to open the .md sibling and select everything

  Background:
    Given a built llmwiki site is served
    And clipboard permissions are granted

  Scenario: Copy button puts the session markdown on the clipboard
    When I open the session "e2e-demo/2026-04-09-e2e-python-demo"
    And I click the "Copy as markdown" button
    Then the clipboard contains "Summary"
    And the clipboard contains "FastAPI"
