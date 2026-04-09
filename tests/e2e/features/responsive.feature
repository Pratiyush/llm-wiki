Feature: Responsive layout across breakpoints
  As a visitor on any device from a phone to a 4K monitor
  I want the layout to adapt without horizontal scroll, cropped
    text, or broken nav
  So I never land on a page that looks broken

  Background:
    Given a built llmwiki site is served

  Scenario Outline: Homepage fits the viewport at every breakpoint
    When I resize the viewport to <width>x<height>
    And I visit the homepage
    Then the body has no horizontal scroll
    And the nav bar is visible
    And the hero heading is visible

    Examples:
      | width | height | device-class |
      | 320   | 568    | tiny-phone   |
      | 375   | 667    | phone        |
      | 414   | 896    | phone-plus   |
      | 768   | 1024   | tablet       |
      | 1024  | 768    | tablet-land  |
      | 1280  | 800    | laptop       |
      | 1440  | 900    | laptop-hidpi |
      | 1920  | 1080   | desktop-fhd  |
      | 2560  | 1440   | desktop-2k   |

  Scenario Outline: Mobile bottom nav appears only below tablet breakpoint
    When I resize the viewport to <width>x<height>
    And I visit the homepage
    Then the mobile bottom nav visibility is <visible>

    Examples:
      | width | height | visible |
      | 375   | 667    | true    |
      | 414   | 896    | true    |
      | 767   | 1024   | true    |
      | 768   | 1024   | false   |
      | 1280  | 800    | false   |
      | 1920  | 1080   | false   |

  Scenario Outline: Session detail page stays readable at every width
    When I resize the viewport to <width>x<height>
    And I open the session "e2e-demo/2026-04-09-e2e-python-demo"
    Then the body has no horizontal scroll
    And at least one "pre > code" element is visible
    And the article main content width stays under viewport width

    Examples:
      | width | height |
      | 375   | 667    |
      | 768   | 1024   |
      | 1280  | 800    |
      | 1920  | 1080   |
