"""Integration tests for GUI components"""

from unittest.mock import Mock, patch
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules directly

# Import status_bar from the core module
from core import status_bar


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

    @patch("status_bar.detect_wm")
    @patch("status_bar.Launcher")
    @patch("status_bar.GLib.timeout_add_seconds")
    def test_middle_box_creation(
        self, mock_timeout, mock_launcher_class, mock_detect_wm
    ):
        """Test that StatusBar creates middle_box during initialization"""
        mock_wm_client = Mock()
        mock_detect_wm.return_value = mock_wm_client

        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_application = Mock()

        # Create status bar
        status_bar_instance = status_bar.StatusBar(application=mock_application)

        # Verify middle_box is created
        assert hasattr(status_bar_instance, "middle_box")
        assert status_bar_instance.middle_box is not None

    @patch("status_bar.detect_wm")
    @patch("status_bar.Launcher")
    @patch("status_bar.GLib.timeout_add_seconds")
    def test_main_box_layout_assembly(
        self, mock_timeout, mock_launcher_class, mock_detect_wm
    ):
        """Test that main_box contains correct layout with middle and spacers"""
        mock_wm_client = Mock()
        mock_detect_wm.return_value = mock_wm_client

        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_application = Mock()

        # Create status bar
        status_bar_instance = status_bar.StatusBar(application=mock_application)

        # Get the children of main_box
        children = []
        child = status_bar_instance.main_box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()

        # Should have 5 children: left_box, left_spacer, middle_box, right_spacer, right_box
        assert len(children) == 5
        assert children[0] == status_bar_instance.left_box
        assert children[1].get_hexpand() is True  # left_spacer
        assert children[2] == status_bar_instance.middle_box
        assert children[3].get_hexpand() is True  # right_spacer
        assert children[4] == status_bar_instance.right_box

    @patch("status_bar.detect_wm")
    @patch("status_bar.Launcher")
    @patch("status_bar.GLib.timeout_add_seconds")
    @patch("status_bar.BAR_LAYOUT", {"left": [], "middle": ["time"], "right": []})
    def test_middle_modules_construction(
        self, mock_timeout, mock_launcher_class, mock_detect_wm
    ):
        """Test that middle modules are constructed correctly"""
        mock_wm_client = Mock()
        mock_detect_wm.return_value = mock_wm_client

        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_application = Mock()

        # Create status bar with time in middle
        status_bar_instance = status_bar.StatusBar(application=mock_application)

        # Verify time_label is created (since time is in middle)
        assert hasattr(status_bar_instance, "time_label")
        assert status_bar_instance.time_label is not None

        # Verify middle_box has the time widget
        children = []
        child = status_bar_instance.middle_box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()

        # Should have time_label (and possibly separators)
        assert len(children) >= 1
        # The time_label should be in the children
        assert status_bar_instance.time_label in children

    @patch("status_bar.detect_wm")
    @patch("status_bar.Launcher")
    @patch("status_bar.GLib.timeout_add_seconds")
    @patch("status_bar.BAR_LAYOUT", {"left": [], "middle": ["time"], "right": []})
    def test_module_checks_include_middle(
        self, mock_timeout, mock_launcher_class, mock_detect_wm
    ):
        """Test that module update checks include middle modules"""
        mock_wm_client = Mock()
        mock_detect_wm.return_value = mock_wm_client

        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_application = Mock()

        # Create status bar with time in middle
        status_bar.StatusBar(application=mock_application)

        # Verify timeout was called for time (which is in middle)
        # Should have 4 calls: time, battery, binding_state, emacs_clock
        # But since time is in middle, it should still be included
        assert mock_timeout.call_count == 4

    @patch("status_bar.detect_wm")
    @patch("status_bar.Launcher")
    @patch("status_bar.GLib.timeout_add_seconds")
    @patch(
        "status_bar.BAR_LAYOUT",
        {"left": [], "middle": ["time", "battery"], "right": []},
    )
    def test_construct_modules_middle_with_separators(
        self, mock_timeout, mock_launcher_class, mock_detect_wm
    ):
        """Test that construct_modules adds separators between middle modules"""
        mock_wm_client = Mock()
        mock_detect_wm.return_value = mock_wm_client

        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_application = Mock()

        # Create status bar with multiple modules in middle
        status_bar_instance = status_bar.StatusBar(application=mock_application)

        # Get children of middle_box
        children = []
        child = status_bar_instance.middle_box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()

        # Should have: time_label, separator, battery_label
        assert len(children) == 3
        assert children[0] == status_bar_instance.time_label
        assert children[1].get_text() == " | "  # separator
        assert children[2] == status_bar_instance.battery_label
