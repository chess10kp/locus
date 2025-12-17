"""Integration tests for GUI components"""

from unittest.mock import Mock, patch
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules directly
import importlib.util

# Load status_bar
status_bar_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "status_bar.py"
)
status_bar_spec = importlib.util.spec_from_file_location("status_bar", status_bar_path)
if status_bar_spec and status_bar_spec.loader:
    status_bar = importlib.util.module_from_spec(status_bar_spec)
    status_bar_spec.loader.exec_module(status_bar)
else:
    raise ImportError("Could not load status_bar module")


class TestStatusBarIntegration:
    """Test status bar integration"""

    @patch("status_bar.detect_wm")
    @patch("status_bar.Launcher")
    @patch("status_bar.GLib.timeout_add_seconds")
    def test_status_bar_initialization(
        self, mock_timeout, mock_launcher_class, mock_detect_wm
    ):
        """Test status bar initializes correctly"""
        mock_wm_client = Mock()
        mock_detect_wm.return_value = mock_wm_client

        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_application = Mock()

        # Create status bar
        status_bar_instance = status_bar.StatusBar(application=mock_application)

        # Verify initialization
        assert status_bar_instance.wm_client == mock_wm_client
        assert status_bar_instance.launcher == mock_launcher
        mock_detect_wm.assert_called_once()
        mock_launcher_class.assert_called_once_with(application=mock_application)

        # Verify timeout callbacks are set up
        assert mock_timeout.call_count == 4  # time, battery, binding_state, emacs_clock

    @patch("status_bar.dt")
    def test_update_time(self, mock_dt):
        """Test time update functionality"""
        mock_now = Mock()
        mock_now.strftime.return_value = "14:30"
        mock_dt.now.return_value = mock_now

        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        status_bar_instance.update_time()

        status_bar_instance.time_label.set_text.assert_called_once_with("14:30")
        mock_now.strftime.assert_called_once_with("%H:%M")

    @patch("status_bar.get_battery_status")
    def test_update_battery(self, mock_get_battery):
        """Test battery update functionality"""
        mock_get_battery.return_value = "85%"

        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        status_bar_instance.update_battery()

        status_bar_instance.battery_label.set_text.assert_called_once_with("85%")
        mock_get_battery.assert_called_once()

    @patch("status_bar.subprocess.run")
    def test_update_binding_state_sway(self, mock_run):
        """Test binding state update with sway"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '{"name": "resize"}'

        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        status_bar_instance.update_binding_state()

        status_bar_instance.binding_state_label.set_text.assert_called_once_with(
            "[resize]"
        )
        mock_run.assert_called_once_with(
            ["swaymsg", "-t", "get_binding_state"],
            capture_output=True,
            text=True,
            timeout=2,
        )

    @patch("status_bar.subprocess.run")
    def test_update_binding_state_default(self, mock_run):
        """Test binding state update with default mode"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '{"name": "default"}'

        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        status_bar_instance.update_binding_state()

        status_bar_instance.binding_state_label.set_text.assert_called_once_with("")

    @patch("status_bar.subprocess.run")
    def test_update_binding_state_exception(self, mock_run):
        """Test binding state update handles exceptions"""
        mock_run.side_effect = Exception("Command failed")

        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        status_bar_instance.update_binding_state()

        status_bar_instance.binding_state_label.set_text.assert_called_once_with("")

    @patch("status_bar.subprocess.run")
    def test_update_emacs_clock_success(self, mock_run):
        """Test Emacs clock update with success"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '"Working on project"'

        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        status_bar_instance.update_emacs_clock()

        status_bar_instance.emacs_clock_label.set_text.assert_called_once_with(
            "Working on project"
        )
        mock_run.assert_called_once_with(
            [
                "emacsclient",
                "-e",
                '(progn (require \'org-clock) (if (org-clocking-p) org-clock-heading ""))',
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )

    @patch("status_bar.subprocess.run")
    def test_update_emacs_clock_failure(self, mock_run):
        """Test Emacs clock update handles failure"""
        mock_run.return_value.returncode = 1

        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        status_bar_instance.update_emacs_clock()

        status_bar_instance.emacs_clock_label.set_text.assert_called_once_with("")

    def test_update_custom_message(self):
        """Test custom message update"""
        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        status_bar_instance.update_custom_message("Test message")

        status_bar_instance.custom_message_label.set_text.assert_called_once_with(
            "Test message"
        )

    def test_on_launcher_clicked(self):
        """Test launcher button click"""
        mock_application = Mock()
        mock_launcher = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher", return_value=mock_launcher),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        mock_button = Mock()
        status_bar_instance.on_launcher_clicked(mock_button)

        mock_launcher.show_launcher.assert_called_once()

    def test_time_callback(self):
        """Test time update callback returns True"""
        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        result = status_bar_instance.update_time_callback()
        assert result is True

    def test_battery_callback(self):
        """Test battery update callback returns True"""
        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        result = status_bar_instance.update_battery_callback()
        assert result is True

    def test_binding_state_callback(self):
        """Test binding state update callback returns True"""
        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        result = status_bar_instance.update_binding_state_callback()
        assert result is True

    def test_emacs_clock_callback(self):
        """Test Emacs clock update callback returns True"""
        mock_application = Mock()

        with (
            patch("status_bar.detect_wm"),
            patch("status_bar.Launcher"),
            patch("status_bar.GLib.timeout_add_seconds"),
        ):
            status_bar_instance = status_bar.StatusBar(application=mock_application)

        result = status_bar_instance.update_emacs_clock_callback()
        assert result is True
