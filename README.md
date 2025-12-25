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

## Statusbar Modules

The Locus statusbar features a modular, plugin-like architecture that makes it easy to add custom modules without modifying core code.

### Overview

The Go implementation provides a flexible module system with:
- **Type-safe interfaces**: Compile-time guarantees with Go interfaces
- **Event-driven updates**: Socket and IPC event listeners for real-time updates
- **Flexible configuration**: TOML-based configuration per module
- **CSS styling**: Full CSS class support for theming
- **Multiple update modes**: STATIC, PERIODIC, EVENT_DRIVEN, and ON_DEMAND

### Built-in Modules

- **TimeModule**: Display current time (PERIODIC)
- **BatteryModule**: Show battery status and percentage (PERIODIC)
- **WorkspacesModule**: Display workspace indicators from window manager (EVENT_DRIVEN)
- **LauncherModule**: Button to trigger application launcher (STATIC)
- **CustomMessageModule**: Display custom messages via IPC (ON_DEMAND)

### Adding New Modules

To add a new module to the statusbar:

1. Create a new Go file in `internal/statusbar/modules/`
2. Implement the `Module` interface from `internal/statusbar/interface.go`
3. Create a `ModuleFactory` for your module
4. Auto-register your factory in the `init()` function
5. Configure your module in the TOML config file

For detailed documentation on the statusbar module architecture, including step-by-step guides and examples, see [STATUSBAR_ARCHITECTURE.md](docs/STATUSBAR_ARCHITECTURE.md).

### Quick Example

```go
package modules

import (
    "github.com/gotk3/gotk3/gtk"
    "github.com/sigma/locus-go/internal/statusbar"
)

type MyModule struct {
    *statusbar.BaseModule
    widget *gtk.Label
    data   string
}

func NewMyModule() *MyModule {
    return &MyModule{
        BaseModule: statusbar.NewBaseModule("my_module", statusbar.UpdateModePeriodic),
        data:       "Hello World",
    }
}

func (m *MyModule) CreateWidget() (gtk.IWidget, error) {
    label, _ := gtk.LabelNew(m.data)
    m.widget = label
    return label, nil
}

func (m *MyModule) UpdateWidget(widget gtk.IWidget) error {
    if label, ok := widget.(*gtk.Label); ok {
        label.SetText(m.data)
    }
    return nil
}

func init() {
    registry := statusbar.DefaultRegistry()
    factory := &MyModuleFactory{}
    registry.RegisterFactory(factory)
}
```

### Configuration

Modules are configured in `config.toml`:

```toml
[status_bar]
height = 20
modules = ["time", "battery", "my_module"]

[status_bar.module_configs.time]
format = "%H:%M:%S"
interval = 1
css_classes = ["time-module"]

[status_bar.module_configs.my_module]
data = "Custom Value"
interval = 10
css_classes = ["my-module"]
```

See [STATUSBAR_ARCHITECTURE.md](docs/STATUSBAR_ARCHITECTURE.md) for comprehensive documentation on:
- Module interface and lifecycle
- Event listener system
- Creating custom modules
- Event-driven modules
- Styling and theming
- Best practices and troubleshooting

# Acknowledgements

- ULauncher for launcher optimizations
