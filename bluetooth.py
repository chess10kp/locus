import subprocess


def bluetooth_power_on():
    try:
        result = subprocess.run(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=5
        )
        return "Powered: yes" in result.stdout
    except Exception:
        return False


def bluetooth_scan_on():
    try:
        result = subprocess.run(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=5
        )
        return "Discovering: yes" in result.stdout
    except Exception:
        return False


def bluetooth_pairable_on():
    try:
        result = subprocess.run(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=5
        )
        return "Pairable: yes" in result.stdout
    except Exception:
        return False


def bluetooth_discoverable_on():
    try:
        result = subprocess.run(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=5
        )
        return "Discoverable: yes" in result.stdout
    except Exception:
        return False


def bluetooth_get_devices():
    try:
        result = subprocess.run(
            ["bluetoothctl", "devices"], capture_output=True, text=True, timeout=5
        )
        devices = []
        for line in result.stdout.splitlines():
            if line.startswith("Device "):
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    mac = parts[1]
                    name = parts[2]
                    devices.append((mac, name))
        return devices
    except Exception:
        return []


def bluetooth_device_connected(mac):
    try:
        result = subprocess.run(
            ["bluetoothctl", "info", mac], capture_output=True, text=True, timeout=5
        )
        return "Connected: yes" in result.stdout
    except Exception:
        return False


def bluetooth_toggle_power():
    if bluetooth_power_on():
        subprocess.run(["bluetoothctl", "power", "off"], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "power", "on"], timeout=5)


def bluetooth_toggle_scan():
    if bluetooth_scan_on():
        subprocess.run(["bluetoothctl", "scan", "off"], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "scan", "on"], timeout=5)


def bluetooth_toggle_pairable():
    if bluetooth_pairable_on():
        subprocess.run(["bluetoothctl", "pairable", "off"], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "pairable", "on"], timeout=5)


def bluetooth_toggle_discoverable():
    if bluetooth_discoverable_on():
        subprocess.run(["bluetoothctl", "discoverable", "off"], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "discoverable", "on"], timeout=5)


def bluetooth_toggle_connection(mac):
    if bluetooth_device_connected(mac):
        subprocess.run(["bluetoothctl", "disconnect", mac], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "connect", mac], timeout=5)
