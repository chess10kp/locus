"""Unit tests for launcher functionality"""

from unittest.mock import Mock, patch
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules directly
import importlib.util

# Load calc_launcher
calc_launcher_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "calc_launcher.py"
)
calc_launcher_spec = importlib.util.spec_from_file_location(
    "calc_launcher", calc_launcher_path
)
if calc_launcher_spec and calc_launcher_spec.loader:
    calc_launcher = importlib.util.module_from_spec(calc_launcher_spec)
    calc_launcher_spec.loader.exec_module(calc_launcher)
else:
    raise ImportError("Could not load calc_launcher module")

# Load bluetooth_launcher
bluetooth_launcher_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bluetooth_launcher.py"
)
bluetooth_launcher_spec = importlib.util.spec_from_file_location(
    "bluetooth_launcher", bluetooth_launcher_path
)
if bluetooth_launcher_spec and bluetooth_launcher_spec.loader:
    bluetooth_launcher = importlib.util.module_from_spec(bluetooth_launcher_spec)
    bluetooth_launcher_spec.loader.exec_module(bluetooth_launcher)
else:
    raise ImportError("Could not load bluetooth_launcher module")


class TestCalcLauncher:
    """Test calculator launcher"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_launcher = Mock()
        self.mock_launcher.list_box = Mock()
        self.mock_launcher.scrolled = Mock()
        self.mock_launcher.current_apps = []
        self.mock_launcher.METADATA = {}

        # Mock the get_vadjustment method
        mock_vadj = Mock()
        self.mock_launcher.scrolled.get_vadjustment.return_value = mock_vadj

        self.calc_launcher = calc_launcher.CalcLauncher(self.mock_launcher)

    @patch("calc_launcher.sanitize_expr")
    @patch("calc_launcher.evaluate_calculator")
    def test_populate_success(self, mock_evaluate, mock_sanitize):
        """Test successful calculation population"""
        mock_sanitize.return_value = "2+2"
        mock_evaluate.return_value = ("4.0", None)

        mock_button = Mock()
        self.mock_launcher.create_button_with_metadata.return_value = mock_button

        self.calc_launcher.populate("2+2")

        mock_sanitize.assert_called_once_with("2+2")
        mock_evaluate.assert_called_once_with("2+2")
        self.mock_launcher.create_button_with_metadata.assert_called_once_with(
            "Result: 4.0", ""
        )
        mock_button.connect.assert_called_once_with(
            "clicked", self.calc_launcher.on_result_clicked, "4.0"
        )
        self.mock_launcher.list_box.append.assert_called_once_with(mock_button)
        assert self.mock_launcher.current_apps == []

    @patch("calc_launcher.sanitize_expr")
    @patch("calc_launcher.evaluate_calculator")
    def test_populate_error(self, mock_evaluate, mock_sanitize):
        """Test error handling in calculation population"""
        mock_sanitize.return_value = "invalid"
        mock_evaluate.return_value = (None, "Invalid syntax")

        mock_button = Mock()
        self.mock_launcher.create_button_with_metadata.return_value = mock_button

        self.calc_launcher.populate("invalid")

        mock_sanitize.assert_called_once_with("invalid")
        mock_evaluate.assert_called_once_with("invalid")
        self.mock_launcher.create_button_with_metadata.assert_called_once_with(
            "Error: Invalid syntax", ""
        )
        # Error buttons should not have click handlers
        mock_button.connect.assert_not_called()

    @patch("calc_launcher.subprocess.run")
    def test_on_result_clicked_wl_copy_success(self, mock_run):
        """Test successful clipboard copy with wl-copy"""
        mock_run.return_value.returncode = 0
        mock_button = Mock()

        self.calc_launcher.on_result_clicked(mock_button, "4.0")

        mock_run.assert_called_once_with(["wl-copy", "4.0"], check=True)
        self.mock_launcher.hide.assert_called_once()

    @patch("calc_launcher.subprocess.run")
    def test_on_result_clicked_xclip_fallback(self, mock_run):
        """Test clipboard copy fallback to xclip"""
        # First call fails (wl-copy), second succeeds (xclip)
        mock_run.side_effect = [
            Mock(side_effect=Exception("wl-copy failed")),
            Mock(returncode=0),
        ]
        mock_button = Mock()

        self.calc_launcher.on_result_clicked(mock_button, "4.0")

        assert mock_run.call_count == 2
        mock_run.assert_any_call(["wl-copy", "4.0"], check=True)
        mock_run.assert_any_call(
            ["xclip", "-selection", "clipboard"],
            input="4.0".encode(),
            check=True,
        )
        self.mock_launcher.hide.assert_called_once()

    @patch("calc_launcher.subprocess.run")
    def test_on_result_clicked_both_fail(self, mock_run):
        """Test when both clipboard methods fail"""
        mock_run.side_effect = Exception("Both failed")
        mock_button = Mock()

        # Should not raise exception, just print error
        self.calc_launcher.on_result_clicked(mock_button, "4.0")

        assert mock_run.call_count == 2
        self.mock_launcher.hide.assert_called_once()


class TestBluetoothLauncher:
    """Test Bluetooth launcher"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_launcher = Mock()
        self.mock_launcher.list_box = Mock()
        self.mock_launcher.current_apps = []
        self.mock_launcher.METADATA = {"bluetooth": "test_metadata"}
        self.mock_launcher.selected_row = None

        self.bt_launcher = bluetooth_launcher.BluetoothLauncher(self.mock_launcher)

    @patch("bluetooth_launcher.bluetooth_power_on")
    @patch("bluetooth_launcher.bluetooth_scan_on")
    @patch("bluetooth_launcher.bluetooth_pairable_on")
    @patch("bluetooth_launcher.bluetooth_discoverable_on")
    @patch("bluetooth_launcher.bluetooth_get_devices")
    @patch("bluetooth_launcher.bluetooth_device_connected")
    def test_populate(
        self,
        mock_connected,
        mock_devices,
        mock_discoverable,
        mock_pairable,
        mock_scan,
        mock_power,
    ):
        """Test Bluetooth menu population"""
        mock_power.return_value = True
        mock_scan.return_value = False
        mock_pairable.return_value = True
        mock_discoverable.return_value = False
        mock_devices.return_value = [("AA:BB:CC:DD:EE:FF", "Test Device")]
        mock_connected.return_value = True

        mock_button = Mock()
        self.mock_launcher.create_button_with_metadata.return_value = mock_button

        self.bt_launcher.populate()

        # Check status items
        # Expected: ["Power: on", "Scan: off", "Pairable: on", "Discoverable: off", "Test Device: Connected (AA:BB:CC:DD:EE:FF)"]

        assert self.mock_launcher.create_button_with_metadata.call_count == 5
        assert self.mock_launcher.list_box.append.call_count == 5
        assert self.mock_launcher.current_apps == []

    @patch("bluetooth_launcher.bluetooth_toggle_power")
    def test_on_bluetooth_clicked_power(self, mock_toggle):
        """Test clicking power toggle"""
        mock_button = Mock()

        self.bt_launcher.on_bluetooth_clicked(mock_button, "Power: on")

        mock_toggle.assert_called_once()

    @patch("bluetooth_launcher.bluetooth_toggle_scan")
    def test_on_bluetooth_clicked_scan(self, mock_toggle):
        """Test clicking scan toggle"""
        mock_button = Mock()

        self.bt_launcher.on_bluetooth_clicked(mock_button, "Scan: off")

        mock_toggle.assert_called_once()

    @patch("bluetooth_launcher.bluetooth_toggle_pairable")
    def test_on_bluetooth_clicked_pairable(self, mock_toggle):
        """Test clicking pairable toggle"""
        mock_button = Mock()

        self.bt_launcher.on_bluetooth_clicked(mock_button, "Pairable: on")

        mock_toggle.assert_called_once()

    @patch("bluetooth_launcher.bluetooth_toggle_discoverable")
    def test_on_bluetooth_clicked_discoverable(self, mock_toggle):
        """Test clicking discoverable toggle"""
        mock_button = Mock()

        self.bt_launcher.on_bluetooth_clicked(mock_button, "Discoverable: off")

        mock_toggle.assert_called_once()

    @patch("bluetooth_launcher.bluetooth_toggle_connection")
    def test_on_bluetooth_clicked_device(self, mock_toggle):
        """Test clicking device item"""
        mock_button = Mock()

        self.bt_launcher.on_bluetooth_clicked(
            mock_button, "Test Device: Disconnected (AA:BB:CC:DD:EE:FF)"
        )

        mock_toggle.assert_called_once_with("AA:BB:CC:DD:EE:FF")
        self.mock_launcher.selected_row = None
        self.mock_launcher.populate_apps.assert_called_once_with(">bluetooth")

    def test_on_bluetooth_clicked_device_invalid_format(self):
        """Test clicking device item with invalid format"""
        mock_button = Mock()

        # Should not crash when format is invalid
        self.bt_launcher.on_bluetooth_clicked(mock_button, "Invalid device format")

        # Should still try to refresh
        self.mock_launcher.selected_row = None
        self.mock_launcher.populate_apps.assert_called_once_with(">bluetooth")
