# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import logging
import time
from typing import Optional, Any, Dict

from gi.repository import GLib
from .config import CUSTOM_LAUNCHERS, METADATA, LAUNCHER_CONFIG
from .search_models import (
    ResultType,
    AppSearchResult,
    CommandSearchResult,
    LauncherSearchResult,
    LoadingSearchResult,
    GridSearchResult,
)
from .wrapped_result import WrappedSearchResult

logger = logging.getLogger("LauncherSearch")


class LauncherSearch:
    """Manages search and population logic for the Launcher."""

    def __init__(self, launcher):
        self.launcher = launcher

    def get_filtered_apps(self, filter_text):
        """Get filtered apps using the new optimized fuzzy search."""
        max_results = LAUNCHER_CONFIG["search"]["max_results"]

        # Track search performance
        start_time = time.time()

        # Use the new optimized app loader with fuzzy search
        results = self.launcher._app_loader.search_apps(filter_text, max_results)

        # Record performance
        duration_ms = (time.time() - start_time) * 1000
        self.launcher.perf_monitor.record(
            "search", duration_ms, filter_text, len(results)
        )

        # Log slow searches
        if duration_ms > 50:
            logger.warning(
                f"Slow search '{filter_text}': {duration_ms:.2f}ms ({len(results)} results)"
            )

        return results

    def populate_command_mode(self, command):
        """Show available launchers and custom commands in command mode using optimized ListView."""
        self.launcher.current_apps = []

        if not command:
            # Show all available commands
            all_commands = list(CUSTOM_LAUNCHERS.keys())
            for (
                launcher_name,
                triggers,
            ) in self.launcher.launcher_registry.list_launchers():
                all_commands.extend(triggers)

            index = 1
            for cmd_name in sorted(set(all_commands)):
                if index > 10:  # Show more command results
                    break

                metadata = METADATA.get(cmd_name, "")
                result = LauncherSearchResult(
                    cmd_name, metadata, index if index <= 9 else 0
                )
                self.launcher.list_store.append(WrappedSearchResult(result))
                index += 1

        elif command in CUSTOM_LAUNCHERS:
            # Handle custom launcher from config
            launcher = CUSTOM_LAUNCHERS[command]
            if isinstance(launcher, str):
                # Try to find matching app
                for app in self.launcher.apps:
                    if launcher.lower() in app["name"].lower():
                        metadata = METADATA.get(app["name"], "")
                        result = AppSearchResult(app, 1)
                        self.launcher.list_store.append(WrappedSearchResult(result))
                        self.launcher.current_apps = [app]
                        break
                else:
                    # No app found, run as command
                    result = CommandSearchResult(launcher, 1)
                    self.launcher.list_store.append(WrappedSearchResult(result))
            else:
                metadata = METADATA.get(command, "")
                result = LauncherSearchResult(command, metadata, 1)
                self.launcher.list_store.append(WrappedSearchResult(result))

        else:
            # Find matching commands
            matching_custom = [
                cmd for cmd in CUSTOM_LAUNCHERS if cmd.startswith(command)
            ]
            matching_launchers = []
            for (
                launcher_name,
                triggers,
            ) in self.launcher.launcher_registry.list_launchers():
                for trigger in triggers:
                    if trigger.startswith(command):
                        matching_launchers.append(trigger)

            all_matching = sorted(set(matching_custom + matching_launchers))
            if all_matching:
                index = 1
                for cmd in all_matching:
                    if index > 10:  # Show more command results
                        break

                    metadata = METADATA.get(cmd, "")
                    result = LauncherSearchResult(
                        cmd, metadata, index if index <= 9 else 0
                    )
                    self.launcher.list_store.append(WrappedSearchResult(result))
                    index += 1
            else:
                # No matching commands, offer to run as shell command
                result = CommandSearchResult(command, 1)
                self.launcher.list_store.append(WrappedSearchResult(result))

    def populate_app_mode(self, filter_text):
        self.launcher.current_apps = []
        index = 1
        max_visible = LAUNCHER_CONFIG["performance"]["max_visible_results"]

        # Use cached filtering for better performance
        filtered_apps = self.get_filtered_apps(filter_text)

        # Show loading indicator if background loading and no results yet
        if not filtered_apps and self.launcher.background_loading:
            elapsed = ""
            if self.launcher.loading_start_time:
                elapsed = f" ({time.time() - self.launcher.loading_start_time:.1f}s)"

            loading_text = f"{LAUNCHER_CONFIG['ui']['loading_text']}{elapsed}"
            result = LoadingSearchResult(loading_text)
            self.launcher.list_store.append(WrappedSearchResult(result))
            return

        # Limit results for performance
        visible_apps = filtered_apps[:max_visible]

        for app in visible_apps:
            self.launcher.current_apps.append(app)
            metadata = METADATA.get(app["name"], "")
            result = AppSearchResult(app, index if index <= 9 else 0)
            self.launcher.list_store.append(WrappedSearchResult(result))
            index += 1

        # Add web search fallback if no apps matched and it's plain text (not a command)
        if (
            not self.launcher.list_store.get_n_items()
            and filter_text
            and not filter_text.startswith(">")
            and not self.launcher.launcher_registry._is_custom_prefix_trigger(
                filter_text
            )[0]
        ):
            hook_data = {"type": "web_search", "query": filter_text}
            result = LauncherSearchResult(
                command=f"Search web for '{filter_text}'",
                metadata="Press Enter to search",
                index=1,
                action_data=hook_data,
                prefix=False,  # Don't add ">" prefix since it's not a command
            )
            self.launcher.list_store.append(WrappedSearchResult(result))
            # Auto-select the web search since it's the only result
            self.launcher.selection_model.set_selected(0)

    def populate_apps(self, filter_text=""):
        """Populate the launcher with apps or use registered launchers for commands."""
        # Don't do anything if launcher is being destroyed
        if self.launcher.destroying:
            return

        # Skip if search text hasn't changed significantly
        if filter_text == self.launcher.last_search_text:
            return
        self.launcher.last_search_text = filter_text

        # Check if any registered launcher can handle this input
        trigger, launcher, query = (
            self.launcher.launcher_registry.find_launcher_for_input(filter_text)
        )

        # Set active launcher context for hook disambiguation
        if launcher:
            self.launcher.active_launcher_context = launcher.name
        elif filter_text.startswith(">"):
            self.launcher.active_launcher_context = "command"
        else:
            self.launcher.active_launcher_context = "apps"

        # Update footer based on mode
        if launcher:
            self.launcher.footer_label.set_text(launcher.name.capitalize())
        # Check if it's a traditional command with > prefix
        elif filter_text.startswith(">"):
            command = filter_text[1:].strip()
            if command:
                self.launcher.footer_label.set_text(f"Command: {command}")
            else:
                self.launcher.footer_label.set_text("Commands")
        # Check if it's a custom trigger (has colon or matching trigger)
        else:
            trigger, _ = self.launcher.launcher_registry._is_custom_prefix_trigger(
                filter_text
            )
            if trigger:
                self.launcher.footer_label.set_text(f"Launcher: {trigger}")
            else:
                self.launcher.footer_label.set_text("Applications")

        # IMPORTANT: Set factory BEFORE clearing the listbox
        if launcher:
            size_mode, custom_size = launcher.get_size_mode()
            # Store current launcher reference for grid mode
            if size_mode.name == "GRID":
                self.launcher._current_grid_launcher = launcher
            else:
                self.launcher._current_grid_launcher = None
            self.launcher.ui.apply_size_mode(size_mode, custom_size)
        # Set default factory if no launcher found
        elif filter_text.startswith(">"):
            self.launcher._current_grid_launcher = None
            self.launcher.ui.reset_launcher_size()
            self.launcher.ui.set_default_factory()
        else:
            trigger, _ = self.launcher.launcher_registry._is_custom_prefix_trigger(
                filter_text
            )
            if not trigger:
                self.launcher._current_grid_launcher = None
                self.launcher.ui.reset_launcher_size()
                self.launcher.ui.set_default_factory()

        # Return buttons to pool instead of destroying them
        self.launcher.list_store.remove_all()

        if launcher:
            # Use the registered launcher
            launcher.populate(query, self.launcher)
        elif filter_text.startswith(">"):
            # Command mode but no launcher found - show available commands
            command = filter_text[1:].strip()
            self.populate_command_mode(command)
        else:
            # Default app search mode
            if LAUNCHER_CONFIG["performance"]["batch_ui_updates"]:
                # Use idle callback for better responsiveness
                if self.launcher.idle_callback_id > 0:
                    GLib.source_remove(self.launcher.idle_callback_id)
                self.launcher.idle_callback_id = GLib.idle_add(
                    self._populate_app_mode_idle, filter_text
                )
            else:
                self.populate_app_mode(filter_text)

    def _populate_app_mode_idle(self, filter_text):
        """Populate app mode using idle callback for better performance."""
        self.populate_app_mode(filter_text)
        self.launcher.idle_callback_id = 0
        return False  # Don't repeat

    def add_launcher_result(
        self,
        title: str,
        subtitle: str = "",
        index: int | None = None,
        result_type: ResultType | None = None,
        action_data=None,
        icon_name: str | None = None,
    ):
        """Add a search result from a sublauncher."""
        if result_type is None:
            result_type = ResultType.LAUNCHER

        # Don't prefix launcher results with ">" since they're items within a launcher
        safe_index = 0 if index is None else index
        result = LauncherSearchResult(
            title,
            subtitle,
            safe_index,
            action_data=action_data,
            prefix=False,
            icon_name=icon_name,
        )
        self.launcher.list_store.append(WrappedSearchResult(result))

    def add_wallpaper_result(
        self,
        title: str,
        image_path: str,
        pixbuf=None,
        index: int | None = None,
        action_data=None,
    ):
        """Add a wallpaper search result with image data."""
        from .search_models import WallpaperSearchResult

        result = WallpaperSearchResult(
            title,
            image_path,
            pixbuf=pixbuf,
            index=index if index else 0,
            action_data=action_data,
        )
        self.launcher.list_store.append(WrappedSearchResult(result))

    def add_grid_result(
        self,
        title: str,
        image_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        pixbuf=None,
        index: int | None = None,
        action_data=None,
    ):
        """Add a grid search result with optional image and metadata."""
        result = GridSearchResult(
            title=title,
            image_path=image_path,
            metadata=metadata,
            pixbuf=pixbuf,
            index=index if index is not None else 0,
            action_data=action_data,
        )
        self.launcher.list_store.append(WrappedSearchResult(result))

    def on_search_changed(self, entry):
        """Handle search entry changes with debouncing."""
        # Prevent recursive calls that can cause RecursionError
        if self.launcher._in_search_changed:
            return

        self.launcher._in_search_changed = True
        try:
            if self.launcher.search_timer:
                GLib.source_remove(self.launcher.search_timer)

            # Adaptive debouncing: shorter for small queries, longer for complex ones
            text = entry.get_text()
            base_delay = LAUNCHER_CONFIG["search"]["debounce_delay"]

            if len(text) <= 1:
                debounce_delay = min(base_delay, 50)  # Very fast for single character
            elif len(text) <= 3:
                debounce_delay = min(base_delay, 100)  # Fast for short queries
            else:
                debounce_delay = base_delay  # Standard delay for longer queries

            self.launcher.search_timer = GLib.timeout_add(
                debounce_delay, self._debounced_populate, text
            )
        finally:
            self.launcher._in_search_changed = False

    def _debounced_populate(self, text):
        """Debounced populate callback."""
        self.populate_apps(text)
        self.launcher.search_timer = None
        return False
