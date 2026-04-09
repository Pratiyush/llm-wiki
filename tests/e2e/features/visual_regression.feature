Feature: Visual regression screenshots across breakpoints + themes
  As a maintainer watching for silent CSS regressions
  I want a screenshot captured at every breakpoint + theme combo
  So `pytest --snapshot-update` shows a diff when a change moves pixels

  Background:
    Given a built llmwiki site is served

  Scenario Outline: Capture home page screenshot at <breakpoint> in <theme>
    When I resize the viewport to <width>x<height>
    And I set the theme to "<theme>"
    And I visit the homepage
    Then I capture a screenshot tagged "home-<breakpoint>-<theme>"

    Examples:
      | breakpoint | width | height | theme |
      | phone      | 375   | 667    | light |
      | phone      | 375   | 667    | dark  |
      | tablet     | 768   | 1024   | light |
      | tablet     | 768   | 1024   | dark  |
      | laptop     | 1280  | 800    | light |
      | laptop     | 1280  | 800    | dark  |
      | desktop    | 1920  | 1080   | light |
      | desktop    | 1920  | 1080   | dark  |

  Scenario Outline: Capture session page screenshot at <breakpoint> in <theme>
    When I resize the viewport to <width>x<height>
    And I set the theme to "<theme>"
    And I open the session "e2e-demo/2026-04-09-e2e-python-demo"
    Then I capture a screenshot tagged "session-<breakpoint>-<theme>"

    Examples:
      | breakpoint | width | height | theme |
      | phone      | 375   | 667    | light |
      | tablet     | 768   | 1024   | light |
      | laptop     | 1280  | 800    | dark  |
      | desktop    | 1920  | 1080   | dark  |
