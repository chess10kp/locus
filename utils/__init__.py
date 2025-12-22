"""Utility modules for locus functionality."""

from .calculator import sanitize_expr, evaluate_calculator
from .bookmarks import get_bookmarks
from .bluetooth import (
    bluetooth_power_on,
    bluetooth_scan_on,
    bluetooth_pairable_on,
    bluetooth_discoverable_on,
    bluetooth_get_devices,
    bluetooth_device_connected,
    bluetooth_toggle_power,
    bluetooth_toggle_scan,
    bluetooth_toggle_pairable,
    bluetooth_toggle_discoverable,
    bluetooth_toggle_connection,
)
from .wifi import (
    wifi_power_on,
    wifi_get_saved_networks,
    wifi_scan,
    wifi_get_current_connection,
    wifi_is_connected,
    wifi_toggle_power,
    wifi_connect,
    wifi_disconnect,
    wifi_forget,
)
from .monitor import get_monitors, toggle_monitor
from .wm import detect_wm
from .utils import (
    apply_styles,
    send_status_message,
    get_battery_status,
    load_desktop_apps,
    VBox,
    HBox,
    get_default_styling,
)

__all__ = [
    "sanitize_expr",
    "evaluate_calculator",
    "get_bookmarks",
    "bluetooth_power_on",
    "bluetooth_scan_on",
    "bluetooth_pairable_on",
    "bluetooth_discoverable_on",
    "bluetooth_get_devices",
    "bluetooth_device_connected",
    "bluetooth_toggle_power",
    "bluetooth_toggle_scan",
    "bluetooth_toggle_pairable",
    "bluetooth_toggle_discoverable",
    "bluetooth_toggle_connection",
    "wifi_power_on",
    "wifi_get_saved_networks",
    "wifi_scan",
    "wifi_get_current_connection",
    "wifi_is_connected",
    "wifi_toggle_power",
    "wifi_connect",
    "wifi_disconnect",
    "wifi_forget",
    "get_monitors",
    "toggle_monitor",
    "detect_wm",
    "apply_styles",
    "send_status_message",
    "get_battery_status",
    "load_desktop_apps",
    "VBox",
    "HBox",
    "get_default_styling",
]
