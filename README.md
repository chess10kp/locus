Desktop Shell

## Adding a New Statusbar Module

To add a new module to the statusbar:

1. Create a new Python file in `modules/statusbar/` that implements `StatusbarModuleInterface` from `core/statusbar_interface.py`.

2. Your module class must implement the following abstract methods:
   - `name`: Return a unique string identifier
   - `update_mode`: Return the update mode (STATIC, PERIODIC, EVENT_DRIVEN, or ON_DEMAND)
   - `create_widget()`: Create and return a GTK widget
   - `update(widget)`: Update the widget's content
   - `get_size_mode()`: Return size mode and optional custom size

3. Optional methods you can override:
   - `update_interval`: For PERIODIC modules, return interval in seconds
   - `get_styles()`: Return CSS styles for the module
   - `handles_clicks()` and `handle_click()`: For click handling
   - `handles_ipc_messages()` and `handle_ipc_message()`: For IPC message handling
   - `cleanup()`: Clean up resources when unregistered

4. Add your module to `modules/statusbar/__init__.py`:
   - Import your new module class
   - Add an instance to the `modules` list in `auto_register_modules()`
   - Add the class name to the `__all__` list

5. Example module structure:

```python
from core.statusbar_interface import (
    StatusbarModuleInterface,
    StatusbarUpdateMode,
    StatusbarSizeMode,
)

class MyModule(StatusbarModuleInterface):
    @property
    def name(self) -> str:
        return "my_module"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.STATIC

    def create_widget(self) -> Gtk.Widget:
        label = Gtk.Label()
        self.update(label)
        return label

    def update(self, widget: Gtk.Widget) -> None:
        widget.set_text("Hello World")

    def get_size_mode(self):
        return StatusbarSizeMode.DEFAULT, None
```

6. The module will be automatically registered when the application starts.

# Acknowledgements

- ULauncher for launcher optimizations
