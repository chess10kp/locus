# Adding and Registering a New Launcher

This guide explains how to create and register a custom launcher in Locus. Launchers are modular plugins that extend the system's functionality, allowing users to execute commands, display results, and integrate with external tools.

## Prerequisites

- Basic Python knowledge
- Understanding of Locus architecture (see `core/launcher_registry.py`)
- Access to edit Locus source files

## Launcher Architecture Overview

Launchers inherit from `LauncherInterface` and integrate via:
- **Registry**: Manages launcher instances and triggers
- **Hooks**: Handle user interactions (select, enter, tab)
- **Core**: Provides UI integration methods

Key components:
- `command_triggers`: List of strings to activate the launcher
- `populate(query, launcher_core)`: Adds UI results
- `get_size_mode()`: Returns display size configuration

## Step-by-Step Implementation

### 1. Create the Launcher File

Create `launchers/your_launcher.py`:

```python
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from core.hooks import LauncherHook

# Optional: Define hooks for custom interactions
class YourLauncherHook(LauncherHook):
    def on_select(self, launcher, item_data):
        # Handle item selection (e.g., execute action)
        pass

    def on_enter(self, launcher, text):
        # Handle enter key
        pass

    def on_tab(self, launcher, text):
        # Handle tab completion
        pass

class YourLauncher(LauncherInterface):
    @classmethod
    def check_dependencies(cls):
        # Optional: Check for required tools
        return True, ""  # Return (success, error_message)

    def __init__(self, main_launcher):
        self.launcher = main_launcher
        # Register hook if needed
        self.hook = YourLauncherHook(self)
        main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["yourcommand"]

    @property
    def name(self):
        return "yourcommand"

    def populate(self, query, launcher_core):
        # Add results to UI
        launcher_core.add_launcher_result(
            title="Example Item",
            metadata="Description",
            index=1
        )
        # Add more results as needed

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None
```

### 2. Add Imports

Edit `launchers/__init__.py`:

```python
# Add at the end
from .your_launcher import YourLauncher, YourLauncherHook
```

### 3. Register the Launcher

Edit `core/launcher_window.py` in the `_register_launchers()` method:

```python
# Add import at top
from launchers.your_launcher import YourLauncher

# In the registration list, add:
register_launcher_with_check(YourLauncher)
```

### 4. Optional Configuration

For custom prefixes or metadata, edit `core/config.py`:

```python
# Custom prefix (e.g., "yc:" instead of ">yourcommand")
LAUNCHER_PREFIXES = {
    # ... existing entries
    "yourcommand": ["yc:"],
}

# Metadata for UI descriptions
METADATA = {
    # ... existing entries
    "yourcommand": "Your custom launcher description",
}
```

## Testing and Validation

1. Restart Locus
2. Type `>yourcommand` or your custom prefix
3. Verify results appear in the UI
4. Test interactions (select, enter, tab if implemented)

Common issues:
- Import errors: Check `launchers/__init__.py` and `core/launcher_window.py`
- No results: Ensure `populate()` calls `launcher_core.add_launcher_result()`
- Dependency failures: Check `check_dependencies()` return value

## Advanced Topics

- **Custom Sizes**: Return `LauncherSizeMode.GRID` or `LauncherSizeMode.WALLPAPER` for specialized layouts
- **Async Operations**: Use threads or callbacks in `populate()` for slow operations
- **External Integration**: Call system commands or APIs within `populate()` or hook methods

For examples, see existing launchers like `calc_launcher.py` or `file_launcher.py`.