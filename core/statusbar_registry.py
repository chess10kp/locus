# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import importlib
import inspect
from typing import Dict, List, Optional, Type, Callable
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .statusbar_interface import StatusbarModuleInterface


class ModuleFileWatcher(FileSystemEventHandler):
    """File system watcher for hot-reloading statusbar modules."""

    def __init__(self, registry: 'StatusbarModuleRegistry'):
        self.registry = registry
        self.module_files: Dict[str, str] = {}  # module_name -> file_path

    def register_module_file(self, module_name: str, file_path: str):
        """Register a module file for watching."""
        self.module_files[module_name] = file_path

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = event.src_path
        if not file_path.endswith('.py'):
            return

        # Find which module this file belongs to
        for module_name, registered_path in self.module_files.items():
            if file_path == registered_path:
                print(f"Module file modified: {module_name} at {file_path}")
                self.registry.reload_module(module_name)
                break


class StatusbarModuleRegistry:
    """Central registry for managing statusbar modules with hot-reload support."""

    def __init__(self):
        self._modules: Dict[str, StatusbarModuleInterface] = {}
        self._module_classes: Dict[str, Type[StatusbarModuleInterface]] = {}
        self._module_instances: Dict[str, StatusbarModuleInterface] = {}
        self._module_files: Dict[str, str] = {}  # module_name -> file_path
        self._reload_callbacks: List[Callable[[str, StatusbarModuleInterface], None]] = []

        # Setup file watching for hot-reloading
        self.observer = Observer()
        self.file_watcher = ModuleFileWatcher(self)
        self._watching = False

    def register(self, module: StatusbarModuleInterface) -> None:
        """Register a statusbar module."""
        if module.name in self._modules:
            raise ValueError(f"Module '{module.name}' is already registered")

        self._modules[module.name] = module

        # Store the class and file path for hot-reloading
        module_class = module.__class__
        self._module_classes[module.name] = module_class

        # Get the file path where this module is defined
        try:
            file_path = inspect.getfile(module_class)
            self._module_files[module.name] = file_path
            self.file_watcher.register_module_file(module.name, file_path)

            # Start watching the directory if not already watching
            if not self._watching:
                self._start_file_watching()
        except (TypeError, OSError) as e:
            print(f"Warning: Could not track file for module '{module.name}': {e}")

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

        if name in self._module_files:
            del self._module_files[name]

    def get_module(self, name: str) -> Optional[StatusbarModuleInterface]:
        """Get module by name."""
        return self._modules.get(name)

    def create_instance(self, name: str, **kwargs) -> Optional[StatusbarModuleInterface]:
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

    def reload_module(self, module_name: str) -> bool:
        """Reload a module by name."""
        if module_name not in self._module_classes:
            print(f"Module '{module_name}' not found for reloading")
            return False

        try:
            # Get the file path and module info
            file_path = self._module_files[module_name]
            old_module_class = self._module_classes[module_name]

            # Get the module's import path
            module_path = old_module_class.__module__

            # Reload the module
            if module_path in sys.modules:
                importlib.reload(sys.modules[module_path])

            # Re-import the module class
            module = importlib.import_module(module_path)
            new_module_class = getattr(module, old_module_class.__name__)

            # Update registry with new class
            self._module_classes[module_name] = new_module_class

            # Create new instance
            new_instance = new_module_class()

            # Replace old module with new one
            if module_name in self._modules:
                old_instance = self._modules[module_name]
                old_instance.cleanup()

            self._modules[module_name] = new_instance

            # Call reload callbacks
            for callback in self._reload_callbacks:
                try:
                    callback(module_name, new_instance)
                except Exception as e:
                    print(f"Error in reload callback for module '{module_name}': {e}")

            print(f"Successfully reloaded module '{module_name}'")
            return True

        except Exception as e:
            print(f"Error reloading module '{module_name}': {e}")
            return False

    def add_reload_callback(self, callback: Callable[[str, StatusbarModuleInterface], None]):
        """Add a callback to be called when a module is reloaded."""
        self._reload_callbacks.append(callback)

    def remove_reload_callback(self, callback: Callable[[str, StatusbarModuleInterface], None]):
        """Remove a reload callback."""
        if callback in self._reload_callbacks:
            self._reload_callbacks.remove(callback)

    def _start_file_watching(self):
        """Start watching module files for changes."""
        if self._watching:
            return

        # Watch the modules directory
        modules_dir = Path(__file__).parent.parent / "modules"
        if modules_dir.exists():
            self.observer.schedule(self.file_watcher, str(modules_dir), recursive=True)
            self.observer.start()
            self._watching = True
            print(f"Started watching module files in: {modules_dir}")

    def stop_file_watching(self):
        """Stop watching module files."""
        if self._watching:
            self.observer.stop()
            self.observer.join()
            self._watching = False
            print("Stopped watching module files")

    def __del__(self):
        """Cleanup when registry is destroyed."""
        self.stop_file_watching()


# Global registry instance
statusbar_registry = StatusbarModuleRegistry()

# Import sys for module reloading
import sys