Feature: File Launcher
  As a user
  I want to launch files
  So that I can open documents quickly

  Scenario: Launch a text file
    Given the file launcher is available
    When I select a text file
    Then the file should open in the default editor