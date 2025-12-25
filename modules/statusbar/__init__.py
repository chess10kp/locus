"""
Statusbar modules package.

This package contains statusbar module implementations that follow the plugin interface.
Modules are automatically registered on import.
"""

# Import all statusbar modules to trigger registration
from .launcher_module import LauncherModule
from .time_module import TimeModule
from .battery_module import BatteryModule
from .workspaces_module import WorkspacesModule
from .binding_mode_module import BindingModeModule
from .emacs_clock_module import EmacsClockModule
from .custom_message_module import CustomMessageModule
from .notification_module import NotificationModule


def auto_register_modules():
    """Auto-register all statusbar modules."""
    from core.statusbar_registry import statusbar_registry

    modules = [
        LauncherModule(),
        TimeModule(),
        BatteryModule(),
        WorkspacesModule(),
        BindingModeModule(),
        EmacsClockModule(),
        CustomMessageModule(),
        NotificationModule(),
    ]

    for module in modules:
        try:
            statusbar_registry.register(module)
            print(f"Registered statusbar module: {module.name}")
        except Exception as e:
            print(f"Error registering statusbar module {module.name}: {e}")


# Auto-register on import
auto_register_modules()


__all__ = [
    "LauncherModule",
    "TimeModule",
    "BatteryModule",
    "WorkspacesModule",
    "BindingModeModule",
    "EmacsClockModule",
    "CustomMessageModule",
    "NotificationModule",
]
