# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from utils import (
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
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode


class WifiHook(LauncherHook):
    def __init__(self, launcher):
        self.launcher = launcher

    def on_select(self, launcher, item_data):
        """Handle button clicks for WiFi controls and networks."""
        if not item_data:
            return False

        # Handle both string and dict input
        data_str = (
            item_data if isinstance(item_data, str) else str(item_data.get("", ""))
        )

        if data_str == "Power: toggle":
            wifi_toggle_power()
        elif data_str == "Disconnect":
            wifi_disconnect()
        elif data_str == "Rescan":
            # Trigger a fresh scan
            self.launcher._scan_cache = None
        elif data_str.startswith("Forget:"):
            # Extract SSID from "Forget:SSID"
            ssid = data_str.split(":", 1)[1] if ":" in data_str else None
            if ssid:
                wifi_forget(ssid)
        else:
            # Network item - Extract SSID from (SSID) format
            ssid_start = data_str.rfind("(")
            ssid_end = data_str.rfind(")")
            if ssid_start != -1 and ssid_end != -1 and ssid_end > ssid_start:
                ssid = data_str[ssid_start + 1 : ssid_end]
                if ssid:
                    # If connected, disconnect; otherwise connect
                    if wifi_is_connected(ssid):
                        wifi_disconnect(ssid)
                    else:
                        wifi_connect(ssid)

        # Refresh the menu by re-populating
        launcher.selected_row = None
        launcher.populate_apps(">wifi")
        return True

    def on_enter(self, launcher, text):
        """Handle enter key for WiFi operations."""
        # Same as on_select for WiFi
        return False

    def on_tab(self, launcher, text):
        """Handle tab completion for WiFi commands."""
        # Only handle WiFi commands
        if not text.startswith(">wifi"):
            return None

        text_lower = text.lower()

        # Status items for completion
        power_status = "Power: on" if wifi_power_on() else "Power: off"
        current = wifi_get_current_connection()

        # Build completion list
        completions = []

        # Status items
        if "power" in text_lower or not text:
            completions.append(power_status)
        if "disconnect" in text_lower or (current and not text):
            completions.append("Disconnect")
        if "rescan" in text_lower or not text:
            completions.append("Rescan")

        # Get saved networks for completion
        saved = wifi_get_saved_networks()
        for ssid in saved:
            # Regular connect
            if not text or ssid.lower().startswith(text_lower):
                completions.append(ssid)
            # Forget option
            if not text or "forget" in text_lower:
                forget_option = f"Forget:{ssid}"
                if not text or forget_option.lower().startswith(text_lower):
                    completions.append(forget_option)

        # Get available networks
        available = wifi_scan()
        for net in available:
            ssid = net["ssid"]
            if ssid not in saved and (not text or ssid.lower().startswith(text_lower)):
                completions.append(ssid)

        # Find best match
        matching = [c for c in completions if c.lower().startswith(text_lower)]
        if matching:
            # Prefer exact matches, then shorter completions
            matching.sort(key=lambda x: (0 if x.lower() == text_lower else 1, len(x)))
            return matching[0]

        return None


class WifiLauncher(LauncherInterface):
    @classmethod
    def check_dependencies(cls) -> tuple[bool, str]:
        """Check if required dependencies are available.

        Returns:
            Tuple of (available, error_message)
        """
        from utils import check_nmcli

        if not check_nmcli():
            return False, "nmcli (NetworkManager) not found"
        return True, ""

    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = WifiHook(self)
        self._scan_cache = None
        self._scan_time = 0

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["wifi"]

    @property
    def name(self):
        return "wifi"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def populate(self, query, launcher_core):
        # Status items with Ctrl+number shortcuts
        power_status = "Power: on" if wifi_power_on() else "Power: off"
        current = wifi_get_current_connection()

        status_items = [
            ("Power: toggle", power_status, 1),
            ("Disconnect", "Disconnect", 2 if current else None),
            ("Rescan", "Rescan", 3),
        ]

        for item_data, display, index in status_items:
            metadata = launcher_core.METADATA.get("wifi", "")
            launcher_core.add_launcher_result(
                display, metadata, index=index if index and index <= 9 else None
            )

        # Get saved networks
        saved_networks = wifi_get_saved_networks()

        # Get available networks (with cache to avoid excessive scanning)
        import time

        current_time = time.time()
        if self._scan_cache is None or (current_time - self._scan_time) > 10:
            # Rescan if cache is old or doesn't exist
            self._scan_cache = wifi_scan()
            self._scan_time = current_time

        available_networks = self._scan_cache if self._scan_cache else []

        # Build list of networks to display
        # First show saved networks with their status
        shown_ssids = set()
        index_counter = 4

        for ssid in saved_networks:
            if ssid not in shown_ssids:
                is_current = current == ssid
                status = "Connected" if is_current else "Saved"
                display = f"{status}: {ssid}"
                metadata = launcher_core.METADATA.get("wifi", "")

                # Check signal strength if in available networks
                signal = None
                for net in available_networks:
                    if net["ssid"] == ssid:
                        signal = net["signal"]
                        security = net["security"]
                        if signal:
                            display = f"{status}: {ssid}"
                        break

                launcher_core.add_launcher_result(
                    display,
                    metadata,
                    index=index_counter if index_counter <= 9 else None,
                )
                shown_ssids.add(ssid)
                index_counter += 1
                if index_counter > 9:
                    break

        # Then show available networks that aren't saved
        if index_counter <= 9:
            for net in available_networks:
                ssid = net["ssid"]
                if ssid and ssid not in shown_ssids:
                    signal = net["signal"]
                    security = net["security"]
                    display = f"Available: {ssid}"
                    metadata = launcher_core.METADATA.get("wifi", "")
                    launcher_core.add_launcher_result(
                        display,
                        metadata,
                        index=index_counter if index_counter <= 9 else None,
                    )
                    shown_ssids.add(ssid)
                    index_counter += 1
                    if index_counter > 9:
                        break

        launcher_core.current_apps = []
