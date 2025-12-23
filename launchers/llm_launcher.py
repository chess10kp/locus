# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import json
import threading
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from core.launcher_registry import LauncherInterface, LauncherSizeMode
from core.hooks import LauncherHook
from utils import send_status_message


class LLMProvider:
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str, model: str, endpoint: str):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """Send chat messages and return response."""
        raise NotImplementedError

    def format_messages(self, messages: List[Dict[str, str]]) -> Any:
        """Format messages for this provider's API."""
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""

    def chat(self, messages: List[Dict[str, str]]) -> str:
        import requests

        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}

        # Convert messages to Gemini format
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

        data = {"contents": gemini_messages}

        try:
            response = requests.post(
                self.endpoint, headers=headers, json=data, timeout=30
            )
            response.raise_for_status()

            result = response.json()
            if "candidates" in result and result["candidates"]:
                return result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                raise ValueError("No response content from Gemini")

        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    def format_messages(self, messages: List[Dict[str, str]]) -> Any:
        return messages


class OpenAIProvider(LLMProvider):
    """OpenAI provider."""

    def chat(self, messages: List[Dict[str, str]]) -> str:
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {"model": self.model, "messages": messages, "temperature": 0.7}

        try:
            response = requests.post(
                self.endpoint, headers=headers, json=data, timeout=30
            )
            response.raise_for_status()

            result = response.json()
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"]
            else:
                raise ValueError("No response content from OpenAI")

        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def format_messages(self, messages: List[Dict[str, str]]) -> Any:
        return messages


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider."""

    def chat(self, messages: List[Dict[str, str]]) -> str:
        import requests

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Convert to Claude format
        system_messages = [msg for msg in messages if msg["role"] == "system"]
        user_messages = [msg for msg in messages if msg["role"] != "system"]

        data = {"model": self.model, "max_tokens": 4096, "messages": user_messages}

        if system_messages:
            data["system"] = system_messages[0]["content"]

        try:
            response = requests.post(
                self.endpoint, headers=headers, json=data, timeout=30
            )
            response.raise_for_status()

            result = response.json()
            if "content" in result and result["content"]:
                return result["content"][0]["text"]
            else:
                raise ValueError("No response content from Claude")

        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")

    def format_messages(self, messages: List[Dict[str, str]]) -> Any:
        return messages


class GrokProvider(LLMProvider):
    """xAI Grok provider."""

    def chat(self, messages: List[Dict[str, str]]) -> str:
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {"model": self.model, "messages": messages, "temperature": 0.7}

        try:
            response = requests.post(
                self.endpoint, headers=headers, json=data, timeout=30
            )
            response.raise_for_status()

            result = response.json()
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"]
            else:
                raise ValueError("No response content from Grok")

        except Exception as e:
            raise Exception(f"Grok API error: {str(e)}")

    def format_messages(self, messages: List[Dict[str, str]]) -> Any:
        return messages


class LLMManager:
    """Manages LLM providers and handles API calls."""

    def __init__(self):
        from core.config import LLM_CONFIG

        self.config = LLM_CONFIG
        self.providers = {}
        self.current_provider = self.config.get("default_provider", "gemini")
        self._load_providers()

    def _load_providers(self):
        """Load and initialize providers with API keys."""
        provider_classes = {
            "gemini": GeminiProvider,
            "openai": OpenAIProvider,
            "claude": ClaudeProvider,
            "grok": GrokProvider,
        }

        for name, config in self.config["providers"].items():
            api_key = self._get_api_key(config["api_key_env"])
            if api_key:
                provider_class = provider_classes.get(name)
                if provider_class:
                    self.providers[name] = provider_class(
                        api_key=api_key,
                        model=config["model"],
                        endpoint=config["endpoint"],
                    )

    def _get_api_key(self, env_var: str) -> Optional[str]:
        """Get API key from environment or config file."""
        # Try environment first
        api_key = os.environ.get(env_var)
        if api_key:
            return api_key

        # Try config file as fallback
        config_path = Path.home() / ".config" / "locus" / "llm_config.json"
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                return config.get("api_keys", {}).get(env_var)
        except:
            return None

    def get_available_providers(self) -> List[str]:
        """Return list of providers with valid API keys."""
        return list(self.providers.keys())

    def set_provider(self, provider_name: str) -> bool:
        """Set the current provider."""
        if provider_name in self.providers:
            self.current_provider = provider_name
            return True
        return False

    def get_provider(self) -> Optional[LLMProvider]:
        """Get current provider instance."""
        return self.providers.get(self.current_provider)

    def chat(self, messages: List[Dict[str, str]], callback=None) -> Optional[str]:
        """Send chat message asynchronously."""
        provider = self.get_provider()
        if not provider:
            if callback:
                callback(None, f"No valid API key for {self.current_provider}")
            return None

        def _chat_thread():
            try:
                send_status_message(f"LLM: Thinking with {self.current_provider}...")
                response = provider.chat(messages)
                send_status_message("LLM: Response ready")
                if callback:
                    callback(response, None)
            except Exception as e:
                error_msg = str(e)
                send_status_message(f"LLM Error: {error_msg[:50]}...")
                if callback:
                    callback(None, error_msg)

        thread = threading.Thread(target=_chat_thread, daemon=True)
        thread.start()
        return None  # Async call


class LLMHook(LauncherHook):
    """Hook for handling LLM launcher interactions."""

    def __init__(self, llm_launcher):
        self.llm_launcher = llm_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle button clicks on launcher results."""
        if not item_data or not isinstance(item_data, dict):
            return False

        action = item_data.get("action")
        if action == "send_query":
            query = item_data.get("query", "")
            self.llm_launcher.send_query(query)
            return True
        elif action == "copy_response":
            self.llm_launcher.copy_last_response()
            return True
        elif action == "regenerate":
            self.llm_launcher.regenerate_last()
            return True
        elif action == "clear_history":
            self.llm_launcher.clear_history()
            return True
        elif action == "switch_provider":
            provider = item_data.get("provider")
            self.llm_launcher.switch_provider(provider)
            return True

        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle enter key for special commands and chat."""
        if text.startswith(">ai"):
            cmd = text[4:].strip()
            if cmd == "clear":
                self.llm_launcher.clear_history()
                send_status_message("Chat history cleared")
                return True
            elif cmd == "copy":
                self.llm_launcher.copy_last_response()
                return True
            elif cmd == "regenerate" or cmd == "regen":
                self.llm_launcher.regenerate_last()
                return True
            else:
                # Handle chat commands
                self.llm_launcher.is_chat_mode = True
                if cmd.strip():
                    self.llm_launcher.send_query(cmd)
                else:
                    # Just show chat interface
                    pass
                # Re-show launcher for chat (centered)
                if launcher:
                    # Center the launcher horizontally
                    try:
                        screen = launcher.get_display().get_monitor_at_surface(
                            launcher.get_surface()
                        )
                        if screen:
                            monitor_geometry = screen.get_geometry()
                            center_x = monitor_geometry.width // 2
                            launcher.show_launcher(center_x=center_x)
                        else:
                            launcher.show_launcher()
                    except:
                        launcher.show_launcher()
                return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle tab completion for LLM commands."""
        if not text.startswith(">ai"):
            return None

        # Available commands for tab completion
        commands = [
            "clear",
            "copy",
            "regenerate",
            "regen",
            "provider:gemini",
            "provider:openai",
            "provider:claude",
            "provider:grok",
        ]

        # Find matching commands
        prefix = text[4:].strip()
        matching = [cmd for cmd in commands if cmd.startswith(prefix)]

        if matching:
            return ">ai " + matching[0]

        return None


class LLMLauncher(LauncherInterface):
    """LLM Chat Launcher for AI conversations."""

    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.llm_manager = LLMManager()
        self.hook = LLMHook(self)
        self.chat_history = []
        self.current_query = ""
        self.is_chat_mode = False

        # Register hook
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

        # Load chat history
        self._load_chat_history()

    @property
    def command_triggers(self) -> List[str]:
        return [">ai"]

    @property
    def name(self) -> str:
        return "llm_chat"

    def get_size_mode(self) -> Tuple[LauncherSizeMode, Optional[Tuple[int, int]]]:
        """Return custom size for chat interface."""
        if self.is_chat_mode:
            return LauncherSizeMode.CUSTOM, (1000, 700)
        return LauncherSizeMode.DEFAULT, None

    def handles_enter(self) -> bool:
        return True

    def handle_enter(self, query: str, launcher_core) -> bool:
        """Handle enter key press."""
        # >ai commands are handled by the hook's on_enter method
        return False

    def populate(self, query: str, launcher_core) -> None:
        """Populate launcher results based on query."""
        if query.startswith(">ai"):
            self.is_chat_mode = True
            self._show_chat_interface(launcher_core)
        else:
            # Show provider selection and recent chats
            self._show_main_interface(launcher_core)

    def _show_main_interface(self, launcher_core):
        """Show main LLM launcher interface."""
        available_providers = self.llm_manager.get_available_providers()

        # Show available providers
        for provider in available_providers:
            status = "✓" if provider == self.llm_manager.current_provider else ""
            launcher_core.add_launcher_result(
                title=f"{provider.upper()} {status}",
                subtitle=f"Switch to {provider} AI assistant",
                index=len(launcher_core.current_apps) + 1,
                action_data={"action": "switch_provider", "provider": provider},
            )

        # Show recent chat history if any
        if self.chat_history:
            launcher_core.add_launcher_result(
                title="Continue Chat",
                subtitle=f"Resume conversation ({len(self.chat_history)} messages)",
                index=len(launcher_core.current_apps) + 1,
                action_data={"action": "continue_chat"},
            )

        launcher_core.current_apps = []

    def _show_chat_interface(self, launcher_core):
        """Show chat interface with history and input."""
        # Show chat history
        for i, msg in enumerate(self.chat_history[-10:]):  # Last 10 messages
            role = msg["role"]
            content = (
                msg["content"][:100] + "..."
                if len(msg["content"]) > 100
                else msg["content"]
            )
            icon = "👤" if role == "user" else "🤖"

            launcher_core.add_launcher_result(
                title=f"{icon} {role.title()}", subtitle=content, index=i + 1
            )

        # Show action buttons
        actions = [
            ("Copy Last Response", "copy_response"),
            ("Regenerate", "regenerate"),
            ("Clear History", "clear_history"),
        ]

        for action_title, action_type in actions:
            launcher_core.add_launcher_result(
                title=action_title,
                subtitle=f"AI: {action_type.replace('_', ' ')}",
                index=len(launcher_core.current_apps) + 1,
                action_data={"action": action_type},
            )

        launcher_core.current_apps = []

    def send_query(self, query: str):
        """Send a query to the current LLM provider."""
        if not query.strip():
            return

        # Add user message to history
        self.chat_history.append(
            {"role": "user", "content": query, "timestamp": time.time()}
        )

        # Prepare messages for API
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.chat_history[-10:]
        ]  # Last 10 messages for context

        # Send async request
        def response_callback(response, error):
            if response:
                self.chat_history.append(
                    {
                        "role": "assistant",
                        "content": response,
                        "timestamp": time.time(),
                        "provider": self.llm_manager.current_provider,
                    }
                )
                self._save_chat_history()
                # Re-show launcher with updated chat (centered)
                if self.launcher:
                    # Center the launcher horizontally
                    try:
                        screen = self.launcher.get_display().get_monitor_at_surface(
                            self.launcher.get_surface()
                        )
                        if screen:
                            monitor_geometry = screen.get_geometry()
                            center_x = monitor_geometry.width // 2
                            self.launcher.show_launcher(center_x=center_x)
                        else:
                            self.launcher.show_launcher()
                    except:
                        self.launcher.show_launcher()
            elif error:
                self.chat_history.append(
                    {
                        "role": "assistant",
                        "content": f"Error: {error}",
                        "timestamp": time.time(),
                        "error": True,
                    }
                )
                self._save_chat_history()
                # Re-show launcher with error message (centered)
                if self.launcher:
                    # Center the launcher horizontally
                    try:
                        screen = self.launcher.get_display().get_monitor_at_surface(
                            self.launcher.get_surface()
                        )
                        if screen:
                            monitor_geometry = screen.get_geometry()
                            center_x = monitor_geometry.width // 2
                            self.launcher.show_launcher(center_x=center_x)
                        else:
                            self.launcher.show_launcher()
                    except:
                        self.launcher.show_launcher()

        self.llm_manager.chat(messages, response_callback)

    def copy_last_response(self):
        """Copy the last assistant response to clipboard."""
        for msg in reversed(self.chat_history):
            if msg["role"] == "assistant" and not msg.get("error", False):
                import subprocess

                try:
                    subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=msg["content"].encode(),
                        check=True,
                    )
                    send_status_message("Response copied to clipboard")
                except:
                    send_status_message("Failed to copy to clipboard")
                return
        send_status_message("No response to copy")

    def regenerate_last(self):
        """Regenerate the last assistant response."""
        user_messages = [msg for msg in self.chat_history if msg["role"] == "user"]
        if user_messages:
            last_user_msg = user_messages[-1]["content"]
            # Remove last assistant response if it exists
            if self.chat_history and self.chat_history[-1]["role"] == "assistant":
                self.chat_history.pop()
            self.send_query(last_user_msg)

    def clear_history(self):
        """Clear chat history."""
        self.chat_history = []
        self._save_chat_history()
        send_status_message("Chat history cleared")

    def switch_provider(self, provider: str) -> bool:
        """Switch to a different LLM provider."""
        if self.llm_manager.set_provider(provider):
            send_status_message(f"Switched to {provider}")
            return True
        else:
            available = self.llm_manager.get_available_providers()
            send_status_message(
                f"Provider '{provider}' not available. Available: {', '.join(available)}"
            )
            return False

    def _load_chat_history(self):
        """Load chat history from cache."""
        cache_dir = Path.home() / ".cache" / "locus"
        cache_dir.mkdir(parents=True, exist_ok=True)
        history_file = cache_dir / "llm_history.json"

        try:
            with open(history_file, "r") as f:
                data = json.load(f)
                self.chat_history = data.get("history", [])
                # Restore current provider
                if "current_provider" in data:
                    self.llm_manager.current_provider = data["current_provider"]
        except:
            self.chat_history = []

    def _save_chat_history(self):
        """Save chat history to cache."""
        cache_dir = Path.home() / ".cache" / "locus"
        cache_dir.mkdir(parents=True, exist_ok=True)
        history_file = cache_dir / "llm_history.json"

        data = {
            "history": self.chat_history[-100:],  # Keep last 100 messages
            "current_provider": self.llm_manager.current_provider,
            "timestamp": time.time(),
        }

        try:
            with open(history_file, "w") as f:
                json.dump(data, f, indent=2)
        except:
            pass  # Silently fail if can't save

    def cleanup(self) -> None:
        """Clean up resources."""
        self._save_chat_history()
