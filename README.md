Desktop Shell

## Clipboard History Launcher

The clipboard history launcher allows you to quickly access and select from your recent clipboard history.

### Dependencies

The clipboard history launcher requires `cliphist` and `wl-clipboard`:

```bash
# Install cliphist (Wayland clipboard manager)
go install go.senan.xyz/cliphist@latest

# Install wl-clipboard (Wayland clipboard utilities)
# On Arch: pacman -S wl-clipboard
# On Ubuntu/Debian: apt install wl-clipboard
# On NixOS: nix-env -iA nixpkgs.wl-clipboard
```

### Setup

Add this to your Wayland compositor startup (e.g., Sway, Hyprland):

```bash
# Start clipboard monitoring
exec wl-paste --watch cliphist store
```

This will monitor clipboard changes and store them in cliphist's database.

### Usage

- Launch with `>clipboard` or `cb:`
- Filter history by typing search terms
- Select an item to copy it to clipboard
- Each item shows a preview (up to 100 characters) and timestamp

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
