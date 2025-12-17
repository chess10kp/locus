import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.bluetooth import *


class TestBluetooth:
    """Test Bluetooth functions"""

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_power_on_true(self, mock_run):
        """Test bluetooth_power_on returns True when powered"""
        mock_run.return_value.stdout = "Controller\n\tPowered: yes\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_power_on()
        assert result is True
        mock_run.assert_called_once_with(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=5
        )

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_power_on_false(self, mock_run):
        """Test bluetooth_power_on returns False when not powered"""
        mock_run.return_value.stdout = "Controller\n\tPowered: no\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_power_on()
        assert result is False

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_power_on_exception(self, mock_run):
        """Test bluetooth_power_on handles exceptions"""
        mock_run.side_effect = Exception("Command failed")

        result = bluetooth.bluetooth_power_on()
        assert result is False

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_scan_on_true(self, mock_run):
        """Test bluetooth_scan_on returns True when scanning"""
        mock_run.return_value.stdout = "Controller\n\tDiscovering: yes\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_scan_on()
        assert result is True

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_scan_on_false(self, mock_run):
        """Test bluetooth_scan_on returns False when not scanning"""
        mock_run.return_value.stdout = "Controller\n\tDiscovering: no\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_scan_on()
        assert result is False

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_pairable_on_true(self, mock_run):
        """Test bluetooth_pairable_on returns True when pairable"""
        mock_run.return_value.stdout = "Controller\n\tPairable: yes\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_pairable_on()
        assert result is True

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_pairable_on_false(self, mock_run):
        """Test bluetooth_pairable_on returns False when not pairable"""
        mock_run.return_value.stdout = "Controller\n\tPairable: no\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_pairable_on()
        assert result is False

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_discoverable_on_true(self, mock_run):
        """Test bluetooth_discoverable_on returns True when discoverable"""
        mock_run.return_value.stdout = "Controller\n\tDiscoverable: yes\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_discoverable_on()
        assert result is True

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_discoverable_on_false(self, mock_run):
        """Test bluetooth_discoverable_on returns False when not discoverable"""
        mock_run.return_value.stdout = "Controller\n\tDiscoverable: no\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_discoverable_on()
        assert result is False

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_get_devices(self, mock_run):
        """Test bluetooth_get_devices parses device list correctly"""
        mock_run.return_value.stdout = """Device AA:BB:CC:DD:EE:FF Test Device 1
Device 11:22:33:44:55:66 Test Device 2
Some other line"""
        mock_run.return_value.returncode = 0

        devices = bluetooth.bluetooth_get_devices()
        expected = [
            ("AA:BB:CC:DD:EE:FF", "Test Device 1"),
            ("11:22:33:44:55:66", "Test Device 2"),
        ]
        assert devices == expected

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_get_devices_empty(self, mock_run):
        """Test bluetooth_get_devices returns empty list when no devices"""
        mock_run.return_value.stdout = "No devices"
        mock_run.return_value.returncode = 0

        devices = bluetooth.bluetooth_get_devices()
        assert devices == []

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_get_devices_exception(self, mock_run):
        """Test bluetooth_get_devices handles exceptions"""
        mock_run.side_effect = Exception("Command failed")

        devices = bluetooth.bluetooth_get_devices()
        assert devices == []

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_device_connected_true(self, mock_run):
        """Test bluetooth_device_connected returns True when connected"""
        mock_run.return_value.stdout = "Device AA:BB:CC:DD:EE:FF\n\tConnected: yes\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_device_connected("AA:BB:CC:DD:EE:FF")
        assert result is True
        mock_run.assert_called_once_with(
            ["bluetoothctl", "info", "AA:BB:CC:DD:EE:FF"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_device_connected_false(self, mock_run):
        """Test bluetooth_device_connected returns False when not connected"""
        mock_run.return_value.stdout = "Device AA:BB:CC:DD:EE:FF\n\tConnected: no\n"
        mock_run.return_value.returncode = 0

        result = bluetooth.bluetooth_device_connected("AA:BB:CC:DD:EE:FF")
        assert result is False

    @patch("bluetooth.subprocess.run")
    def test_bluetooth_device_connected_exception(self, mock_run):
        """Test bluetooth_device_connected handles exceptions"""
        mock_run.side_effect = Exception("Command failed")

        result = bluetooth.bluetooth_device_connected("AA:BB:CC:DD:EE:FF")
        assert result is False

    @patch("bluetooth.bluetooth_power_on")
    @patch("bluetooth.subprocess.run")
    def test_bluetooth_toggle_power_off(self, mock_run, mock_power_on):
        """Test bluetooth_toggle_power turns off when currently on"""
        mock_power_on.return_value = True

        bluetooth.bluetooth_toggle_power()
        mock_run.assert_called_once_with(["bluetoothctl", "power", "off"], timeout=5)

    @patch("bluetooth.bluetooth_power_on")
    @patch("bluetooth.subprocess.run")
    def test_bluetooth_toggle_power_on(self, mock_run, mock_power_on):
        """Test bluetooth_toggle_power turns on when currently off"""
        mock_power_on.return_value = False

        bluetooth.bluetooth_toggle_power()
        mock_run.assert_called_once_with(["bluetoothctl", "power", "on"], timeout=5)

    @patch("bluetooth.bluetooth_scan_on")
    @patch("bluetooth.subprocess.run")
    def test_bluetooth_toggle_scan_off(self, mock_run, mock_scan_on):
        """Test bluetooth_toggle_scan turns off when currently on"""
        mock_scan_on.return_value = True

        bluetooth.bluetooth_toggle_scan()
        mock_run.assert_called_once_with(["bluetoothctl", "scan", "off"], timeout=5)

    @patch("bluetooth.bluetooth_scan_on")
    @patch("bluetooth.subprocess.run")
    def test_bluetooth_toggle_scan_on(self, mock_run, mock_scan_on):
        """Test bluetooth_toggle_scan turns on when currently off"""
        mock_scan_on.return_value = False

        bluetooth.bluetooth_toggle_scan()
        mock_run.assert_called_once_with(["bluetoothctl", "scan", "on"], timeout=5)

    @patch("bluetooth.bluetooth_device_connected")
    @patch("bluetooth.subprocess.run")
    def test_bluetooth_toggle_connection_disconnect(self, mock_run, mock_connected):
        """Test bluetooth_toggle_connection disconnects when currently connected"""
        mock_connected.return_value = True

        bluetooth.bluetooth_toggle_connection("AA:BB:CC:DD:EE:FF")
        mock_run.assert_called_once_with(
            ["bluetoothctl", "disconnect", "AA:BB:CC:DD:EE:FF"], timeout=5
        )

    @patch("bluetooth.bluetooth_device_connected")
    @patch("bluetooth.subprocess.run")
    def test_bluetooth_toggle_connection_connect(self, mock_run, mock_connected):
        """Test bluetooth_toggle_connection connects when currently disconnected"""
        mock_connected.return_value = False

        bluetooth.bluetooth_toggle_connection("AA:BB:CC:DD:EE:FF")
        mock_run.assert_called_once_with(
            ["bluetoothctl", "connect", "AA:BB:CC:DD:EE:FF"], timeout=5
        )
