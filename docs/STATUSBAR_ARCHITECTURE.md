# Locus Statusbar Module Architecture

## Overview

The Locus statusbar now features a modular, plugin-like architecture inspired by nwg-panel but adapted for Go's type system. This makes it easy to add new modules without modifying the core statusbar code.

## Core Components

### 1. Module Interface (`interface.go`)

The `Module` interface defines the contract that all statusbar modules must implement:

```go
type Module interface {
    // Identification
    Name() string
    UpdateMode() UpdateMode
    UpdateInterval() time.Duration

    // Widget management - return actual GTK widgets
    CreateWidget() (gtk.IWidget, error)
    UpdateWidget(widget gtk.IWidget) error

    // Lifecycle
    Initialize(config map[string]interface{}) error
    Cleanup() error

    // Events and interaction
    SetupEventListeners() ([]EventListener, error)
    HandlesClicks() bool
    HandleClick(widget gtk.IWidget) bool
    HandlesIPC() bool
    HandleIPC(message string) bool

    // Styling
    GetStyles() string
    GetCSSClasses() []string
}
```

#### Update Modes

- **STATIC**: No automatic updates (e.g., launcher button)
- **PERIODIC**: Updates at regular intervals (e.g., time, battery)
- **EVENT_DRIVEN**: Updates based on external events (e.g., workspaces, binding mode)
- **ON_DEMAND**: Updates only when triggered manually (e.g., custom messages)

### 2. BaseModule

Provides a common implementation that handles boilerplate:

```go
type BaseModule struct {
    name         string
    updateMode   UpdateMode
    interval     time.Duration
    styles       string
    cssClasses   []string
    initialized  bool
    config       map[string]interface{}
    clickHandler func(widget gtk.IWidget) bool
    ipcHandler   func(message string) bool
}
```

### 3. EventListener System (`events.go`)

Provides different types of event listeners:

- **SocketEventListener**: Listen to Unix sockets (e.g., sway, hyprland)
- **IPCEventListener**: Handle IPC messages
- **SignalEventListener**: Respond to system signals
- **TimerEventListener**: Periodic timer events

### 4. Module Registry (`registry.go`)

Central registry that manages module factories and instances:

- Register module factories
- Create module instances with configuration
- Manage module lifecycle
- Handle widget creation and updates
- Route IPC messages and clicks to modules

### 5. Update Scheduler (`scheduler.go`)

Manages module updates based on their update modes:

- Starts periodic timers for PERIODIC modules
- Sets up event listeners for EVENT_DRIVEN modules
- Provides manual update triggering for ON_DEMAND modules
- Handles click and IPC message routing

## Creating a New Module

### Step 1: Define Your Module

```go
type MyModule struct {
    *statusbar.BaseModule
    widget *gtk.Label
    data   string
}
```

### Step 2: Implement Module Interface

```go
func (m *MyModule) CreateWidget() (gtk.IWidget, error) {
    label, err := gtk.LabelNew(m.data)
    if err != nil {
        return nil, err
    }

    helper := &statusbar.WidgetHelper{}
    helper.ApplyStylesToWidget(label, m.GetStyles(), m.GetCSSClasses())

    return label, nil
}

func (m *MyModule) UpdateWidget(widget gtk.IWidget) error {
    label, ok := widget.(*gtk.Label)
    if !ok {
        return nil
    }

    label.SetText(m.data)
    return nil
}

func (m *MyModule) Initialize(config map[string]interface{}) error {
    if err := m.BaseModule.Initialize(config); err != nil {
        return err
    }

    // Load configuration
    if data, ok := config["data"].(string); ok {
        m.data = data
    }

    return nil
}

// Other required methods...
```

### Step 3: Create a Factory

```go
type MyModuleFactory struct{}

func (f *MyModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
    module := NewMyModule()
    if err := module.Initialize(config); err != nil {
        return nil, err
    }
    return module, nil
}

func (f *MyModuleFactory) ModuleName() string {
    return "my_module"
}

func (f *MyModuleFactory) DefaultConfig() map[string]interface{} {
    return map[string]interface{}{
        "data": "default_value",
        "interval": "10s",
        "css_classes": []string{"my-module"},
    }
}

func (f *MyModuleFactory) Dependencies() []string {
    return []string{}
}
```

### Step 4: Auto-Register Your Module

```go
func init() {
    registry := statusbar.DefaultRegistry()
    factory := &MyModuleFactory{}
    if err := registry.RegisterFactory(factory); err != nil {
        panic(err)
    }
}
```

## Event-Driven Modules

For modules that respond to external events (e.g., window manager events):

```go
func (m *MyModule) SetupEventListeners() ([]statusbar.EventListener, error) {
    if m.socketPath == "" {
        return nil, nil
    }

    listener := statusbar.NewSocketEventListener(m.socketPath)
    listener.SetEventHandler(m.handleSocketEvent)

    return []statusbar.EventListener{listener}, nil
}

func (m *MyModule) handleSocketEvent(event string) {
    // Parse event and update state
    // Module will be automatically updated when event triggers
}
```

## Configuration

Modules are configured via the TOML configuration file:

```toml
[status_bar]
height = 20
modules = ["time", "battery", "workspaces", "launcher"]

[status_bar.module_configs.time]
format = "%H:%M:%S"
interval = 1
css_classes = ["time-module"]

[status_bar.module_configs.battery]
interval = 30
show_percentage = true
show_icon = true
css_classes = ["battery-module"]

[status_bar.module_configs.workspaces]
socket_path = "/tmp/sway-ipc.sock"
show_labels = true
css_classes = ["workspaces-module"]
```

## Built-in Modules

### TimeModule (`modules/time.go`)

- **Update Mode**: PERIODIC
- **Config**: `format`, `interval`, `css_classes`
- **Example**: Display current time with custom format

### BatteryModule (`modules/battery.go`)

- **Update Mode**: PERIODIC
- **Config**: `battery_path`, `show_percentage`, `show_icon`, `interval`
- **Example**: Display battery percentage and charging status

### WorkspacesModule (`modules/workspaces.go`)

- **Update Mode**: EVENT_DRIVEN
- **Config**: `socket_path`, `show_labels`, `css_classes`
- **Example**: Display workspace indicators from window manager

### LauncherModule (`modules/launcher.go`)

- **Update Mode**: STATIC
- **Config**: `label`, `css_classes`
- **Example**: Button to trigger application launcher

### CustomMessageModule (`modules/custom_message.go`)

- **Update Mode**: ON_DEMAND
- **Config**: `message`, `timeout`, `css_classes`
- **Example**: Display custom messages via IPC

## Widget Helper

The `WidgetHelper` provides convenient methods for creating styled widgets:

```go
helper := &statusbar.WidgetHelper{}

// Create styled label
label, err := helper.CreateStyledLabel("text", "color: red;", []string{"my-label"})

// Create styled button
button, err := helper.CreateStyledButton("Click me", "", []string{"my-button"})

// Apply styles to existing widget
helper.ApplyStylesToWidget(widget, "color: blue;", []string{"styled"})
```

## Lifecycle

1. **Load**: Factory creates module instance with configuration
2. **Register**: Module is registered in the global registry
3. **Initialize**: Module's `Initialize()` method is called
4. **Create Widget**: Module's `CreateWidget()` creates GTK widget
5. **Schedule**: Scheduler sets up timers or event listeners
6. **Update**: Module is updated based on its update mode
7. **Cleanup**: Module's `Cleanup()` method is called on shutdown

## Best Practices

1. **Use BaseModule**: Extend `BaseModule` for common functionality
2. **Handle Errors**: Always handle errors in CreateWidget and UpdateWidget
3. **Use WidgetHelper**: Leverage helper functions for consistent styling
4. **Configuration**: Provide sensible defaults and validate configuration
5. **Cleanup**: Always clean up resources (close sockets, stop timers)
6. **Thread Safety**: Be careful with shared state, use mutexes if needed
7. **Styling**: Use CSS classes for theming support

## Comparison with nwg-panel

### Similarities

- Modular architecture with factory pattern
- JSON/TOML configuration for modules
- Event-driven updates for window manager integration
- CSS styling support
- IPC message handling

### Improvements in Locus

- **Type Safety**: Go's strong typing prevents runtime errors
- **Performance**: Compiled Go is faster than Python
- **Concurrency**: Better goroutine-based concurrency vs Python threads
- **Interface Design**: Cleaner separation between static, periodic, event-driven, and on-demand updates
- **Error Handling**: More robust error handling throughout

## Future Enhancements

1. **Plugin System**: Load modules from external shared libraries
2. **Hot Reload**: Reload modules without restarting statusbar
3. **Module Dependencies**: Explicit dependency management between modules
4. **Configuration Validation**: Schema-based configuration validation
5. **Module Discovery**: Auto-discover modules from multiple sources
6. **CSS Theme Support**: Advanced theming with CSS variables

## Testing Modules

To test a module:

```bash
# Run locus with custom config
./locus -c config.toml

# Send IPC messages to trigger ON_DEMAND updates
echo '{"module": "custom_message", "message": "Hello!"}' | socat - /tmp/locus_socket
```

## Troubleshooting

### Module Not Loading

- Check module name matches factory `ModuleName()`
- Ensure `init()` function registers the factory
- Verify configuration has no syntax errors
- Check logs for registration errors

### Widget Not Updating

- Verify update mode is correct for your use case
- Check that interval is not too long
- Ensure event listeners are started for EVENT_DRIVEN modules
- Review logs for update errors

### Styling Issues

- Verify CSS classes are being applied
- Check CSS provider is loaded
- Ensure GTK widget supports styling
- Test with simple inline styles first

## Contributing

To add a new module:

1. Create a new file in `internal/statusbar/modules/`
2. Implement the `Module` interface
3. Create a `ModuleFactory` implementation
4. Auto-register in `init()` function
5. Add configuration documentation
6. Test thoroughly

## Examples

See the built-in modules in `internal/statusbar/modules/` for complete examples:

- `time.go` - Simple periodic module
- `battery.go` - Periodic module with system integration
- `workspaces.go` - Event-driven module with socket listening
- `launcher.go` - Static module with click handling
- `custom_message.go` - ON_DEMAND module with IPC handling
