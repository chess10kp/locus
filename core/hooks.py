# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from abc import ABC, abstractmethod
from typing import Any, Optional, List


class LauncherHook(ABC):
    """Base interface for launcher hooks"""

    @abstractmethod
    def on_select(self, launcher, item_data: Any) -> bool:
        """Called when a button is clicked. Return True to handle, False to continue."""
        pass

    @abstractmethod
    def on_enter(self, launcher, text: str) -> bool:
        """Called when enter is pressed. Return True to handle, False to continue."""
        pass

    @abstractmethod
    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Called when tab is pressed. Return new text or None to continue."""
        pass


class HookRegistry:
    """Registry for managing launcher hooks"""

    def __init__(self):
        self.hooks: List[LauncherHook] = []

    def register_hook(self, hook: LauncherHook) -> None:
        """Register a new hook"""
        self.hooks.append(hook)

    def unregister_hook(self, hook: LauncherHook) -> None:
        """Unregister a hook"""
        if hook in self.hooks:
            self.hooks.remove(hook)

    def execute_select_hooks(self, launcher, item_data: Any) -> bool:
        """Execute select hooks in registration order. Return True if any hook handled the event."""
        print(f"execute_select_hooks: item_data={item_data}, hooks={len(self.hooks)}")
        for hook in self.hooks:
            print(f"calling hook {type(hook).__name__}")
            try:
                if hook.on_select(launcher, item_data):
                    print("hook handled")
                    return True
            except Exception as e:
                print(f"Error in select hook: {e}")
                continue
        print("no hook handled")
        return False

    def execute_enter_hooks(self, launcher, text: str) -> bool:
        """Execute enter hooks in registration order. Return True if any hook handled the event."""
        for hook in self.hooks:
            try:
                if hook.on_enter(launcher, text):
                    return True
            except Exception as e:
                print(f"Error in enter hook: {e}")
                continue
        return False

    def execute_tab_hooks(self, launcher, text: str) -> Optional[str]:
        """Execute tab hooks in registration order. Return first non-None result."""
        for hook in self.hooks:
            try:
                result = hook.on_tab(launcher, text)
                if result is not None:
                    return result
            except Exception as e:
                print(f"Error in tab hook: {e}")
                continue
        return None
