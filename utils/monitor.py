import subprocess
import re


def get_monitors():
    """Get list of monitors with their status."""
    try:
        result = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=5)
        monitors = []
        for line in result.stdout.splitlines():
            # Match lines like: HDMI-1 connected primary 1920x1080+0+0 ...
            match = re.match(r"^(\S+) (connected|disconnected)", line)
            if match:
                name = match.group(1)
                status = match.group(2)
                monitors.append((name, status))
        return monitors
    except Exception:
        return []


def monitor_connected(name):
    """Check if a monitor is connected."""
    monitors = get_monitors()
    for mon_name, status in monitors:
        if mon_name == name:
            return status == "connected"
    return False


def toggle_monitor(name):
    """Toggle monitor on/off."""
    if monitor_connected(name):
        # Turn off
        subprocess.run(["xrandr", "--output", name, "--off"], timeout=5)
    else:
        # Turn on with auto settings
        subprocess.run(["xrandr", "--output", name, "--auto"], timeout=5)
