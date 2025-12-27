# Launcher Specification: keybinding-launcher

**Type**: Launcher Implementation
**Feature ID**: 014
**Python Reference**: `python_backup/launchers/[name]_launcher.py`

---

## Launcher Definition

### Triggers
- Primary: `[trigger1]`
- Aliases: `[trigger2]`, `[trigger3]`
- Custom Prefix: `[prefix]:` (optional)

### Purpose
[Describe what this launcher does]

---

## User Stories

### US-001: [User Story] (P1)
[User story in Given/When/Then format]

**Acceptance**:
1. **Given** launcher is available, **When** user types `[trigger]`, **Then** launcher activates
2. **Given** launcher active, **When** user types `[query]`, **Then** [results appear]

---

## Requirements

### Functional
- **FR-001**: Launcher registers with `[trigger1]`, `[trigger2]`
- **FR-002**: `Populate()` returns results matching query
- **FR-003**: Results include [specific data: icon, metadata, etc.]

### Non-Functional
- Performance: Results < 100ms for <1000 items
- Error handling: Graceful fallback on missing dependencies

---

## Implementation Plan

### Go Structure

```go
// internal/launcher/[name].go
package launcher

import (
    "github.com/sigma/locus/internal/core"
)

type [Name]Launcher struct {
    // Fields
}

func New[Name]Launcher(main *core.Launcher) *FileLauncher {
    l = &[Name]Launcher{main: main}
    core.LauncherRegistry.Register(l)
    return l
}

func (l *[Name]Launcher) Name() string { return "[name]" }

func (l *[Name]Launcher) Triggers() []string {
    return []string{"[trigger1]", "[trigger2]"}
}

func (l *[Name]Launcher) Populate(query string, launcher *core.Launcher) error {
    // Implementation
    return nil
}

func (l *[Name]Launcher) GetSizeMode() (SizeMode, *Size) {
    return DefaultMode, nil
}

func (l *[Name]Launcher) Cleanup() {
    // Cleanup
}
```

### Dependencies
- [List required system tools]
- [List Go packages]

---

## Python Analysis

### File: `python_backup/launchers/[name]_launcher.py`

**Key Components**:
1. `populate(query, launcher_core)` - Main search logic
2. `hook.on_select()` - Handle selection
3. Data structures - Result objects

**Go Adaptation**:
- Python: `launcher_core.add_result()` → Go: `launcher.AddResult()`
- Python: dynamic result dicts → Go: `LauncherItem` struct
- Python: GLib signals → Go: GTK signal handlers

---

## Testing

### Unit Tests

```go
func Test[Name]LauncherTriggers(t *testing.T) {
    // Test trigger recognition
}

func Test[Name]LauncherPopulate(t *testing.T) {
    tests := []struct {
        query string
        want  int // expected result count
    }{
        {"test", 5},
        {"", 0},
    }
    // ...
}
```

---

## Configuration

```toml
[launcher.[name]]
# Launcher-specific settings
setting1 = "value"
```