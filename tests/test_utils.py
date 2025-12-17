"""Unit tests for utility functions"""

from unittest.mock import Mock, patch
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the utils module
import utils.utils as utils


class TestUtils:
    """Test utility functions"""

    @patch("utils.subprocess.run")
    def test_get_battery_status_success(self, mock_run):
        """Test successful battery status retrieval"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            """Battery 0: Discharging, 75%, 02:30:00 remaining"""
        )

        result = utils.get_battery_status()

        assert "75%" in result
        mock_run.assert_called_once_with(
            ["acpi", "-b"], capture_output=True, text=True, timeout=5
        )

    @patch("utils.subprocess.run")
    def test_get_battery_status_no_battery(self, mock_run):
        """Test battery status when no battery found"""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = "No battery"

        result = utils.get_battery_status()

        assert result == "No Battery"

    @patch("utils.subprocess.run")
    def test_get_battery_status_exception(self, mock_run):
        """Test battery status handles exceptions"""
        mock_run.side_effect = Exception("Command failed")

        result = utils.get_battery_status()

        assert result == "No Battery"

    @patch("utils.os.listdir")
    @patch("utils.os.path.exists")
    def test_load_desktop_apps(self, mock_exists, mock_listdir):
        """Test loading desktop applications"""
        mock_exists.return_value = True
        mock_listdir.return_value = ["test_app.desktop", "invalid_file.txt"]

        mock_open = Mock()
        mock_open.return_value.__enter__.return_value.read.return_value = """
[Desktop Entry]
Name=Test App
Exec=test-app --option
Icon=test-icon
Categories=Utility;
"""

        with patch("builtins.open", mock_open):
            apps = utils.load_desktop_apps()

        assert len(apps) == 1
        assert apps[0]["name"] == "Test App"
        assert apps[0]["exec"] == "test-app --option"
        assert apps[0]["icon"] == "test-icon"

    @patch("utils.os.listdir")
    @patch("utils.os.path.exists")
    def test_load_desktop_apps_no_directory(self, mock_exists, mock_listdir):
        """Test loading desktop apps when directory doesn't exist"""
        mock_exists.return_value = False

        apps = utils.load_desktop_apps()

        assert apps == []

    @patch("utils.os.listdir")
    @patch("utils.os.path.exists")
    def test_load_desktop_apps_no_display(self, mock_exists, mock_listdir):
        """Test loading desktop apps when no display"""
        mock_exists.return_value = True
        mock_listdir.return_value = []

        with patch.dict(os.environ, {"DISPLAY": ""}):
            apps = utils.load_desktop_apps()

        assert apps == []

    @patch("utils.os.listdir")
    @patch("utils.os.path.exists")
    def test_load_desktop_apps_hidden_entry(self, mock_exists, mock_listdir):
        """Test loading desktop apps skips hidden entries"""
        mock_exists.return_value = True
        mock_listdir.return_value = ["hidden_app.desktop"]

        mock_open = Mock()
        mock_open.return_value.__enter__.return_value.read.return_value = """
[Desktop Entry]
Name=Hidden App
Exec=hidden-app
NoDisplay=true
"""

        with patch("builtins.open", mock_open):
            apps = utils.load_desktop_apps()

        assert len(apps) == 0

    @patch("utils.Gtk.CssProvider")
    @patch("utils.Gtk.StyleContext")
    def test_apply_styles(self, mock_style_context, mock_css_provider):
        """Test applying CSS styles to widgets"""
        mock_widget = Mock()
        mock_provider = Mock()
        mock_css_provider.return_value = mock_provider
        mock_style_context.return_value = Mock()

        utils.apply_styles(mock_widget, "test { color: red; }")

        mock_css_provider.assert_called_once()
        mock_provider.load_from_data.assert_called_once()
        mock_widget.get_style_context.assert_called_once()

    def test_hbox_creation(self):
        """Test HBox helper function"""
        hbox = utils.HBox(spacing=10, hexpand=True)

        assert hbox.props.spacing == 10
        assert hbox.props.hexpand is True

    def test_vbox_creation(self):
        """Test VBox helper function"""
        vbox = utils.VBox(spacing=5, vexpand=False)

        assert vbox.props.spacing == 5
        assert vbox.props.vexpand is False
