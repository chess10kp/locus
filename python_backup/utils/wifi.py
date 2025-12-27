import subprocess


def wifi_power_on():
    """Check if WiFi is enabled."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "WIFI", "radio"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "enabled" in result.stdout.lower()
    except Exception:
        return False


def wifi_get_saved_networks():
    """Get list of saved/known WiFi networks."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        networks = []
        for line in result.stdout.splitlines():
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    name, conn_type = parts
                    if conn_type == "802-11-wireless" and name:
                        networks.append(name)
        return networks
    except Exception:
        return []


def wifi_scan():
    """Scan for available WiFi networks and return them as list of dicts."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,ACTIVE", "dev", "wifi", "list", "--rescan", "yes"],
            capture_output=True,
            text=True,
            timeout=30,  # Scanning can take longer
        )
        networks = []
        seen_ssids = set()
        for line in result.stdout.splitlines():
            if line and ":" in line:
                parts = line.split(":", 3)
                if len(parts) == 4:
                    ssid, signal, security, active = parts
                    # Skip empty SSIDs and duplicates
                    if ssid and ssid not in seen_ssids:
                        seen_ssids.add(ssid)
                        networks.append({
                            "ssid": ssid,
                            "signal": int(signal) if signal.isdigit() else 0,
                            "security": security if security else "Open",
                            "active": active == "yes",
                        })
        return networks
    except Exception:
        return []


def wifi_get_current_connection():
    """Get the currently connected WiFi network SSID."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if line.startswith("yes:"):
                ssid = line.split(":", 1)[1] if ":" in line else None
                return ssid if ssid else None
        return None
    except Exception:
        return None


def wifi_is_connected(ssid):
    """Check if a specific network is currently connected."""
    try:
        current = wifi_get_current_connection()
        return current == ssid
    except Exception:
        return False


def wifi_toggle_power():
    """Toggle WiFi power on/off."""
    if wifi_power_on():
        subprocess.run(["nmcli", "radio", "wifi", "off"], timeout=5)
    else:
        subprocess.run(["nmcli", "radio", "wifi", "on"], timeout=5)


def wifi_connect(ssid):
    """Connect to a WiFi network. Uses external dialog for password if needed."""
    try:
        # First try to connect as a saved connection
        result = subprocess.run(
            ["nmcli", "con", "up", ssid],
            capture_output=True,
            timeout=30,
        )
        # If that fails, try as new connection (will prompt for password if needed)
        if result.returncode != 0:
            subprocess.run(
                ["nmcli", "dev", "wifi", "connect", ssid],
                timeout=30,
            )
        return True
    except Exception:
        return False


def wifi_disconnect(ssid=None):
    """Disconnect from current WiFi network or specific network."""
    try:
        if ssid:
            subprocess.run(["nmcli", "con", "down", ssid], timeout=10)
        else:
            # Get current connection and disconnect
            current = wifi_get_current_connection()
            if current:
                subprocess.run(["nmcli", "con", "down", current], timeout=10)
            else:
                # Alternative: disconnect all wifi
                subprocess.run(["nmcli", "dev", "disconnect", "iface", "wlan0"], timeout=10)
    except Exception:
        pass


def wifi_forget(ssid):
    """Remove/delete a saved WiFi network."""
    try:
        subprocess.run(["nmcli", "con", "delete", ssid], timeout=5)
    except Exception:
        pass
