# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import subprocess
from typing import Any, Optional
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from core.config import SEARCH_ENGINES, DEFAULT_SEARCH_ENGINE, URL_OPENER


class WebHook(LauncherHook):
    def __init__(self, web_launcher):
        self.web_launcher = web_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle search engine selection and fallback web search"""
        if isinstance(item_data, str) and item_data.startswith("engine:"):
            engine_name = item_data.split(":", 1)[1]
            self.web_launcher.set_engine(engine_name)
            launcher.hide()
            return True

        # Handle fallback web search results from main launcher
        if isinstance(item_data, dict) and item_data.get("type") == "web_search":
            query = item_data.get("query", "")
            if query:
                self.web_launcher.search(query)
                launcher.hide()
                return True

        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle search query - only for explicit web search intent"""
        # Handle explicit >web command
        if text.startswith(">web"):
            query = text[4:].strip()  # Remove ">web"
            if query:
                self.web_launcher.search(query)
                launcher.hide()
                return True
            return False

        query = text.strip()

        # Check for explicit web search intent
        text_lower = text.lower()
        is_web_intent = (
            "http" in text_lower
            or "www" in text_lower
            or text_lower.startswith("search ")
            or any(
                engine in text_lower
                for engine in ["google", "duckduckgo", "bing", "yahoo"]
            )
        )

        if query and is_web_intent:
            self.web_launcher.search(query)
            launcher.hide()
            return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle tab completion for search engines"""
        # Only handle web commands
        if not text.startswith(">web"):
            return None

        text_lower = text.lower()
        # Get the query part after >web
        if text == ">web" or text == ">web ":
            return ">web "

        # Check for search engine prefix
        query = text[4:].strip()  # Remove ">web"
        if ":" in query:
            engine = query.split(":", 1)[0].lower()
            # Complete engine name
            for engine_name in SEARCH_ENGINES.keys():
                if engine_name.startswith(engine):
                    return f">web {engine_name}:"
        else:
            # Complete engine names
            for engine_name in SEARCH_ENGINES.keys():
                if engine_name.startswith(query):
                    return f">web {engine_name}:"

        return None


class WebLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = WebHook(self)
        self.current_engine = DEFAULT_SEARCH_ENGINE
        self.search_history = []

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["web"]

    @property
    def name(self):
        return "web"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def handles_enter(self):
        return True

    def set_engine(self, engine_name: str):
        """Set the current search engine."""
        if engine_name in SEARCH_ENGINES:
            self.current_engine = engine_name
            print(f"Search engine set to: {engine_name}")
        else:
            print(f"Unknown search engine: {engine_name}")

    def search(self, query: str):
        """Perform a web search."""
        # Check if query specifies an engine (e.g., "duckduckgo:cats")
        if ":" in query:
            parts = query.split(":", 1)
            engine = parts[0].lower()
            search_query = parts[1].strip()
            if engine in SEARCH_ENGINES:
                url = SEARCH_ENGINES[engine].format(search_query)
            else:
                # Use default engine if engine not found
                url = SEARCH_ENGINES[self.current_engine].format(query)
        else:
            # Use current engine
            url = SEARCH_ENGINES[self.current_engine].format(query)

        # Add to history
        self.search_history.append(query)

        # Open the URL
        self.open_url(url)

    def open_url(self, url: str):
        """Open a URL in the browser."""
        try:
            # Clean environment for child process
            env = os.environ.copy()
            env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes
            env.pop("MALLOC_CHECK_", None)  # Remove malloc check for child processes
            env.pop(
                "MALLOC_PERTURB_", None
            )  # Remove malloc perturb for child processes

            if URL_OPENER:
                # Use configured browser
                subprocess.Popen([URL_OPENER, url], start_new_session=True, env=env)
            else:
                # Use xdg-open to let system decide
                subprocess.Popen(["xdg-open", url], start_new_session=True, env=env)
        except Exception as e:
            print(f"Failed to open URL: {e}")

    def populate(self, query: str, launcher_core) -> None:
        """Show search engine options or search history."""
        # If query is empty or just the trigger, show engines and history
        if not query:
            # Show search engines
            launcher_core.add_launcher_result(
                "Select a search engine or type your query",
                "Current: " + self.current_engine,
            )

            # Show available search engines
            for engine_name, engine_url in SEARCH_ENGINES.items():
                icon = "🔍" if engine_name == self.current_engine else "•"
                launcher_core.add_launcher_result(
                    f"{icon} {engine_name}",
                    f"engine:{engine_name}",
                )

            # Show recent searches
            if self.search_history:
                launcher_core.add_launcher_result("Recent searches", "")
                for item in reversed(self.search_history[-5:]):
                    launcher_core.add_launcher_result(item, "")
        else:
            # Parse query for engine selection
            if query.startswith(":"):
                # Engine selection mode
                engine_name = query[1:].lower()
                matching_engines = [
                    e for e in SEARCH_ENGINES.keys() if e.startswith(engine_name)
                ]
                if len(matching_engines) == 1:
                    launcher_core.add_launcher_result(
                        f"Search with {matching_engines[0]}",
                        f"engine:{matching_engines[0]}",
                    )
                else:
                    for engine in matching_engines:
                        launcher_core.add_launcher_result(
                            f"• {engine}",
                            f"engine:{engine}",
                        )
            elif ":" in query:
                # Engine specified in query (e.g., "duckduckgo:cats")
                parts = query.split(":", 1)
                engine = parts[0]
                search_term = parts[1].strip()
                if engine in SEARCH_ENGINES:
                    launcher_core.add_launcher_result(
                        f"Search '{search_term}' with {engine}",
                        "",
                    )
                else:
                    launcher_core.add_launcher_result(
                        f"Unknown engine: {engine}",
                        "",
                    )
            else:
                # Normal search - show what will be searched
                launcher_core.add_launcher_result(
                    f"Search for '{query}' with {self.current_engine}",
                    "",
                )
                launcher_core.add_launcher_result(
                    "Press Enter to search",
                    "",
                )
