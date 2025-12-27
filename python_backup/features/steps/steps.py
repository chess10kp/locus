from behave import given, when, then
import os
from unittest.mock import patch
from launchers.file_launcher import FileLauncher


@given("the file launcher is available")
def step_impl(context):
    context.launcher = FileLauncher()


@when("I select a text file")
def step_impl(context):
    # Create a test file
    test_file = "/tmp/test_file_launcher.txt"
    with open(test_file, "w") as f:
        f.write("test content")
    context.test_file = test_file
    with patch("subprocess.Popen") as mock_popen:
        context.launcher.open_file(test_file)
        context.mock_popen = mock_popen


@then("the file should open in the default editor")
def step_impl(context):
    # Check that xdg-open was called
    context.mock_popen.assert_called_once_with(
        ["xdg-open", context.test_file],
        start_new_session=True,
        stdout=-3,  # subprocess.DEVNULL
        stderr=-3,
    )
