# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from typing import Any, Dict, List, Optional, Tuple, Callable
from gi.repository import Gtk, GLib

from .statusbar_interface import StatusbarModuleInterface, StatusbarUpdateMode
from .statusbar_registry import statusbar_registry


class StatusbarModuleManager:
    """Manager for statusbar module lifecycle."""

    def __init__(self, status_bar):
        self.status_bar = status_bar
        self.module_widgets: Dict[str, Gtk.Widget] = {}
        self.module_instances: Dict[str, StatusbarModuleInterface] = {}
        self.update_sources: Dict[str, int] = {}  # GLib source IDs
        self.event_listeners: Dict[str, List[Any]] = {}

    def create_module(
        self, module_name: str, config: Optional[Dict] = None
    ) -> Optional[Gtk.Widget]:
        """Create a module widget and start its update lifecycle."""
        module = statusbar_registry.get_module(module_name)
        if not module:
            return None

        try:
            # Create instance with config if provided
            if config:
                instance = statusbar_registry.create_instance(module_name, **config)
            else:
                instance = statusbar_registry.create_instance(module_name)

            if not instance:
                return None

            # Create widget
            widget = instance.create_widget()
            if not widget:
                return None

            # Apply custom styles if provided
            styles = instance.get_styles()
            if styles:
                self._apply_styles(widget, styles)

            # Store references
            self.module_widgets[module_name] = widget
            self.module_instances[module_name] = instance

            # Start update lifecycle based on update mode
            self._start_module_updates(module_name, instance)

            # Set up click handlers if needed
            if instance.handles_clicks():
                if hasattr(widget, "connect"):
                    # Use 'clicked' for buttons, 'button-press-event' for other widgets
                    if isinstance(widget, Gtk.Button):
                        widget.connect(
                            "clicked",
                            lambda w: self._on_module_click(w, None, module_name),
                        )
                    else:
                        widget.connect(
                            "button-press-event", self._on_module_click, module_name
                        )

            return widget

        except Exception as e:
            return None

    def destroy_module(self, module_name: str):
        """Destroy a module and clean up its resources."""
        # Stop updates
        self._stop_module_updates(module_name)

        # Clean up event listeners
        if module_name in self.event_listeners:
            self.event_listeners[module_name].clear()
            del self.event_listeners[module_name]

        if module_name in self.module_widgets:
            del self.module_widgets[module_name]

        # Clean up instance
        if module_name in self.module_instances:
            instance = self.module_instances[module_name]
            instance.cleanup()
            del self.module_instances[module_name]

    def update_module(self, module_name: str):
        """Manually trigger an update for a specific module."""
        if module_name in self.module_instances and module_name in self.module_widgets:
            instance = self.module_instances[module_name]
            widget = self.module_widgets[module_name]
            try:
                instance.update(widget)
            except Exception as e:
                pass

    def handle_ipc_message(self, message: str) -> bool:
        """Route IPC message to appropriate modules."""
        handled = False
        for module_name, instance in self.module_instances.items():
            if instance.handles_ipc_messages():
                widget = self.module_widgets.get(module_name)
                if widget:
                    try:
                        if instance.handle_ipc_message(message, widget):
                            handled = True
                    except Exception as e:
                        pass

        return handled

    def get_module_widget(self, module_name: str) -> Optional[Gtk.Widget]:
        """Get the widget for a specific module."""
        return self.module_widgets.get(module_name)

    def get_module_instance(
        self, module_name: str
    ) -> Optional[StatusbarModuleInterface]:
        """Get the instance for a specific module."""
        return self.module_instances.get(module_name)

    def list_active_modules(self) -> List[str]:
        """Get list of all active module names."""
        return list(self.module_instances.keys())

    def _start_module_updates(
        self, module_name: str, instance: StatusbarModuleInterface
    ):
        """Start the update lifecycle for a module based on its update mode."""
        update_mode = instance.update_mode

        if update_mode == StatusbarUpdateMode.STATIC:
            # No updates needed for static modules
            pass

        elif update_mode == StatusbarUpdateMode.PERIODIC:
            interval = instance.update_interval or 60  # Default to 60 seconds
            source_id = GLib.timeout_add_seconds(
                interval, self._periodic_update_callback, module_name
            )
            self.update_sources[module_name] = source_id

        elif update_mode == StatusbarUpdateMode.EVENT_DRIVEN:
            # Set up event listeners (module-specific)
            self._setup_event_listeners(module_name, instance)

        elif update_mode == StatusbarUpdateMode.ON_DEMAND:
            # Updates only when requested
            pass

    def _stop_module_updates(self, module_name: str):
        """Stop the update lifecycle for a module."""
        if module_name in self.update_sources:
            source_id = self.update_sources[module_name]
            GLib.source_remove(source_id)
            del self.update_sources[module_name]

        # Clean up event listeners
        if module_name in self.event_listeners:
            for listener in self.event_listeners[module_name]:
                # Try to clean up listener if it has a cleanup method
                if hasattr(listener, "cleanup"):
                    listener.cleanup()
            del self.event_listeners[module_name]

    def _periodic_update_callback(self, module_name: str) -> bool:
        """Callback for periodic module updates."""
        self.update_module(module_name)
        return True  # Continue the timeout

    def _setup_event_listeners(
        self, module_name: str, instance: StatusbarModuleInterface
    ):
        """Set up event listeners for event-driven modules."""
        # This would be module-specific based on what events they need
        # For example, workspaces module would listen to WM events
        listeners = []

        # Check if module has specific event setup method
        if hasattr(instance, "setup_event_listeners"):
            try:
                module_listeners = instance.setup_event_listeners(self.status_bar)
                if module_listeners:
                    listeners.extend(module_listeners)
            except Exception as e:
                pass

        self.event_listeners[module_name] = listeners

    def _on_module_click(self, widget: Gtk.Widget, event, module_name: str):
        """Handle click events on module widgets."""
        if module_name in self.module_instances:
            instance = self.module_instances[module_name]
            try:
                return instance.handle_click(widget, event)
            except Exception as e:
                pass

        return False  # Event not handled

    def _apply_styles(self, widget: Gtk.Widget, css: str):
        """Apply CSS styles to a widget."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        style_context = widget.get_style_context()
        style_context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def cleanup(self):
        """Clean up all modules and stop updates."""
        # Destroy all modules
        for module_name in list(self.module_instances.keys()):
            self.destroy_module(module_name)
