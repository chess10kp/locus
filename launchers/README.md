# Adding New Launchers to Locus

This guide explains how to add new launchers to the Locus launcher system.

## Overview

Launchers in Locus are modular components that provide quick access to various system actions, utilities, or applications. Each launcher inherits from a base `Launcher` class and is registered with the launcher registry.

## Steps to Add a New Launcher

### 1. Create the Launcher Module

Create a new Python file in the `launchers/` directory. The file should contain a class that inherits from `Launcher`.

Example structure:

```python
from core.launcher import Launcher

class MyNewLauncher(Launcher):
    def __init__(self):
        super().__init__()
        self.name = "My New Launcher"
        self.description = "Description of what this launcher does"
        self.icon = "icon-name"  # Optional: icon identifier

    def launch(self):
        # Implement the launch logic here
        # This is called when the launcher is activated
        pass
```

### 2. Implement the Required Methods

At minimum, your launcher class must:

- Inherit from `core.launcher.Launcher`
- Override the `launch()` method with your implementation
- Set the `name` and `description` attributes

### 3. Register the Launcher

In `launchers/__init__.py`, import your new launcher class and register it using the launcher registry.

Example:

```python
from core.launcher_registry import register_launcher
from .my_new_launcher import MyNewLauncher

register_launcher(MyNewLauncher())
```

### 4. Test the Launcher

After adding the launcher:

1. Restart the Locus application
2. Verify the launcher appears in the launcher list
3. Test that activating it performs the expected action

## Example: Calculator Launcher

See `launchers/calc_launcher.py` for a complete example of a launcher that opens a calculator application.

## Best Practices

- Keep launcher implementations lightweight and focused on a single purpose
- Handle errors gracefully in the `launch()` method
- Use descriptive names and provide clear descriptions
- Test on your target platform to ensure compatibility

## Sending Data to the Statusbar

Launchers can send messages to the statusbar to display temporary or persistent information using the `send_status_message` function.

### Basic Usage

```python
from utils import send_status_message

# Send a simple message to the statusbar
send_status_message("Hello from launcher!")

# Send formatted status information
send_status_message(f"Timer: {remaining_time}")
```

### Status Message Format

- Messages are displayed in the statusbar until replaced or cleared
- Clear the statusbar by sending an empty message: `send_status_message("")`
- For persistent status, send periodic updates
- Messages prefixed with "status:" are treated specially by some modules

### Example in a Launcher

```python
def update_status(self, message: str):
    """Update the statusbar with a message."""
    from utils import send_status_message
    send_status_message(f"MyLauncher: {message}")

def some_action(self):
    # Perform action...
    self.update_status("Action completed")
    # Clear after 3 seconds
    GLib.timeout_add_seconds(3, lambda: send_status_message(""))
```

## Available Utilities

You can import and use utilities from the `utils/` directory, such as `app_launcher.py` for launching applications, `send_status_message` for statusbar updates, or other modules as needed.