# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from typing import Dict, List, Optional, Type

from .statusbar_interface import StatusbarModuleInterface


class StatusbarModuleRegistry:
    """Central registry for managing statusbar modules."""

    def __init__(self):
        self._modules: Dict[str, StatusbarModuleInterface] = {}
        self._module_classes: Dict[str, Type[StatusbarModuleInterface]] = {}
        self._module_instances: Dict[str, StatusbarModuleInterface] = {}

    def register(self, module: StatusbarModuleInterface) -> None:
        """Register a statusbar module."""
        if module.name in self._modules:
            raise ValueError(f"Module '{module.name}' is already registered")

        self._modules[module.name] = module

        # Store the class for instance creation
        module_class = module.__class__
        self._module_classes[module.name] = module_class

    def unregister(self, name: str) -> None:
        """Unregister a module by name."""
        if name in self._modules:
            module = self._modules[name]
            module.cleanup()
            del self._modules[name]

        if name in self._module_instances:
            instance = self._module_instances[name]
            instance.cleanup()
            del self._module_instances[name]

        if name in self._module_classes:
            del self._module_classes[name]

    def get_module(self, name: str) -> Optional[StatusbarModuleInterface]:
        """Get module by name."""
        return self._modules.get(name)

    def create_instance(
        self, name: str, **kwargs
    ) -> Optional[StatusbarModuleInterface]:
        """Create a new instance of a module."""
        module_class = self._module_classes.get(name)
        if not module_class:
            return None

        try:
            instance = module_class(**kwargs)
            self._module_instances[name] = instance
            return instance
        except Exception as e:
            print(f"Error creating instance of module '{name}': {e}")
            return None

    def get_all_modules(self) -> List[StatusbarModuleInterface]:
        """Get all registered modules."""
        return list(self._modules.values())

    def get_modules_by_update_mode(self, update_mode) -> List[StatusbarModuleInterface]:
        """Get all modules with specific update mode."""
        from .statusbar_interface import StatusbarUpdateMode

        return [m for m in self._modules.values() if m.update_mode == update_mode]

    def list_modules(self) -> List[str]:
        """Get list of all registered module names."""
        return list(self._modules.keys())


# Global registry instance
statusbar_registry = StatusbarModuleRegistry()
