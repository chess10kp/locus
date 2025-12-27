# Implementation Plan: Clipboard Launcher

**Feature ID**: 015
**Go Version**: 1.23+
**Estimated Effort**: Medium

---

## Summary

Implement a clipboard launcher that tracks clipboard history, stores entries persistently, and allows quick access and pasting of previously copied content.

---

## Constitution Compliance Check

- [x] **Article I**: Go best practices
  - Package naming: `clipboard`
  - Error handling: explicit returns for all I/O operations
  - Concurrency: Use goroutine for clipboard watching, channel for shutdown

- [x] **Article II**: Architecture principles
  - Clean architecture: `internal/launcher/clipboard.go`
  - Plugin registration: `registry.Register(clipboardLauncher)`
  - IPC exposure: `clipboard:get`, `clipboard:clear` commands

- [x] **Article III**: Testing standards
  - Test coverage target: >80%
  - Test types: unit (tracker, storage), integration (launcher workflow)

- [x] **Article IV**: Performance requirements
  - Clipboard detection: < 100ms
  - Search filtering: < 50ms for 1000 entries
  - Storage: SQLite with indexes

- [x] **Article V**: Configuration
  - Config section: `[launcher.clipboard]`
  - Defaults: history_size=100, storage_path="~/.local/share/locus/clipboard.db"

---

## Architecture

### Package Structure

```
internal/
├── launcher/
│   ├── clipboard.go              # Main launcher implementation
│   └── clipboard_test.go         # Tests
├── clipboard/                    # New package for clipboard utilities
│   ├── tracker.go                # Clipboard change detection
│   ├── storage.go                # History persistence (SQLite)
│   └── storage_test.go
```

### Interface Definitions

```go
// ClipboardTracker monitors clipboard changes
type ClipboardTracker interface {
    // Watch starts monitoring clipboard changes
    Watch(ctx context.Context) (<-chan ClipboardEvent, error)
    // Stop stops monitoring
    Stop() error
}

// ClipboardStorage manages clipboard history
type ClipboardStorage interface {
    Add(entry ClipboardEntry) error
    Get(limit int) ([]ClipboardEntry, error)
    Search(query string, limit int) ([]ClipboardEntry, error)
    Clear() error
}
```

### Data Flow

```
wl-paste --watch → ClipboardTracker → Channel → ClipboardStorage (SQLite)
                                                                  ↓
                                              ClipboardLauncher.populate() → UI
```

---

## Implementation Details

### Component 1: Clipboard Tracker

**File**: `internal/clipboard/tracker.go`

```go
type ClipboardTracker struct {
    cmd     *exec.Cmd
    ctx     context.Context
    cancel  context.CancelFunc
    events  chan ClipboardEvent
}

type ClipboardEvent struct {
    Content string
    Type    ContentType // Text, Image, etc.
    Time    time.Time
}

func NewClipboardTracker() *ClipboardTracker {
    ctx, cancel := context.WithCancel(context.Background())
    return &ClipboardTracker{
        ctx:    ctx,
        cancel: cancel,
        events: make(chan ClipboardEvent, 10),
    }
}

func (t *ClipboardTracker) Watch() (<-chan ClipboardEvent, error) {
    t.cmd = exec.CommandContext(t.ctx, "wl-paste", "--watch", "type")
    stdout, err := t.cmd.StdoutPipe()
    if err != nil {
        return nil, err
    }

    if err := t.cmd.Start(); err != nil {
        return nil, err
    }

    // Goroutine to read clipboard changes
    go func() {
        scanner := bufio.NewScanner(stdout)
        for scanner.Scan() {
            t.detectChange()
        }
    }()

    return t.events, nil
}

func (t *ClipboardTracker) Stop() error {
    t.cancel()
    if t.cmd != nil {
        return t.cmd.Wait()
    }
    return nil
}
```

**Error Handling**: Return error if `wl-paste` not available

**Concurrency Considerations**: Separate goroutine for watching, channel for events

---

### Component 2: Clipboard Storage

**File**: `internal/clipboard/storage.go`

```go
import (
    "database/sql"
    _ "modernc.org/sqlite"
)

type ClipboardStorage struct {
    db *sql.DB
}

type ClipboardEntry struct {
    ID        int64
    Content   string
    Type      string
    Timestamp time.Time
}

func NewClipboardStorage(path string) (*ClipboardStorage, error) {
    db, err := sql.Open("sqlite", path)
    if err != nil {
        return nil, err
    }

    // Create table
    _, err = db.Exec(`
        CREATE TABLE IF NOT EXISTS clipboard_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            type TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON clipboard_history(timestamp DESC);
    `)
    if err != nil {
        return nil, err
    }

    return &ClipboardStorage{db: db}, nil
}

func (s *ClipboardStorage) Add(entry ClipboardEntry) error {
    _, err := s.db.Exec(
        "INSERT INTO clipboard_history (content, type, timestamp) VALUES (?, ?, ?)",
        entry.Content, entry.Type, entry.Timestamp.Unix(),
    )
    return err
}

func (s *ClipboardStorage) Search(query string, limit int) ([]ClipboardEntry, error) {
    rows, err := s.db.Query(`
        SELECT id, content, type, timestamp
        FROM clipboard_history
        WHERE content LIKE ?
        ORDER BY timestamp DESC
        LIMIT ?`,
        "%"+query+"%", limit,
    )
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var entries []ClipboardEntry
    for rows.Next() {
        var e ClipboardEntry
        var ts int64
        if err := rows.Scan(&e.ID, &e.Content, &e.Type, &ts); err != nil {
            return nil, err
        }
        e.Timestamp = time.Unix(ts, 0)
        entries = append(entries, e)
    }
    return entries, nil
}
```

**Error Handling**: Return SQL errors to caller

**Concurrency Considerations**: SQLite with WAL mode for concurrent reads

---

### Component 3: Clipboard Launcher

**File**: `internal/launcher/clipboard.go`

```go
import (
    "github.com/sigma/locus/internal/clipboard"
    "github.com/sigma/locus/internal/core"
)

type ClipboardLauncher struct {
    tracker  *clipboard.Tracker
    storage  *clipboard.Storage
    running  bool
}

func NewClipboardLauncher(main *core.Launcher) *ClipboardLauncher {
    storage, err := clipboard.NewStorage(getConfigPath())
    if err != nil {
        log.Printf("Failed to init clipboard storage: %v", err)
        return nil
    }

    tracker := clipboard.NewTracker()

    l := &ClipboardLauncher{
        tracker: tracker,
        storage: storage,
    }

    core.LauncherRegistry.Register(l)

    // Start tracking in background
    go l.trackClipboard()

    return l
}

func (l *ClipboardLauncher) Name() string { return "clipboard" }

func (l *ClipboardLauncher) Triggers() []string {
    return []string{"clipboard", "clip", "c"}
}

func (l *ClipboardLauncher) Populate(query string, launcher *core.Launcher) error {
    entries, err := l.storage.Search(query, 20)
    if err != nil {
        return err
    }

    for i, entry := range entries {
        preview := entry.Content
        if len(preview) > 100 {
            preview = preview[:97] + "..."
        }

        launcher.AddResult(core.LauncherItem{
            Title:    fmt.Sprintf("[%s] %s", entry.Time.Format("15:04"), preview),
            Subtitle: entry.Type,
            Index:    i + 1,
            Data:     entry,
        })
    }
    return nil
}

func (l *ClipboardLauncher) OnSelect(item core.LauncherItem) error {
    entry := item.Data.(clipboard.ClipboardEntry)
    cmd := exec.Command("wl-copy", entry.Content)
    return cmd.Run()
}

func (l *ClipboardLauncher) Cleanup() {
    l.tracker.Stop()
}

func (l *ClipboardLauncher) trackClipboard() {
    events, err := l.tracker.Watch()
    if err != nil {
        return
    }

    for event := range events {
        l.storage.Add(clipboard.ClipboardEntry{
            Content: event.Content,
            Type:    string(event.Type),
            Time:    event.Time,
        })
    }
}
```

---

## Testing Strategy

### Unit Tests

**File**: `internal/clipboard/storage_test.go`

```go
func TestClipboardStorage(t *testing.T) {
    // Use in-memory SQLite
    storage, err := NewClipboardStorage(":memory:")
    require.NoError(t, err)

    // Test Add
    entry := ClipboardEntry{
        Content:   "test content",
        Type:      "text/plain",
        Timestamp: time.Now(),
    }
    err = storage.Add(entry)
    require.NoError(t, err)

    // Test Get
    entries, err := storage.Get(10)
    require.NoError(t, err)
    assert.Len(t, entries, 1)
    assert.Equal(t, "test content", entries[0].Content)

    // Test Search
    results, err := storage.Search("test", 10)
    require.NoError(t, err)
    assert.Len(t, results, 1)
}
```

**File**: `internal/launcher/clipboard_test.go`

```go
func TestClipboardLauncherTriggers(t *testing.T) {
    launcher := NewClipboardLauncher(nil)
    assert.Equal(t, "clipboard", launcher.Name())
    assert.Contains(t, launcher.Triggers(), "c")
}
```

### Integration Tests

Mock clipboard behavior using temporary files and subprocess testing.

---

## IPC Integration

### Commands

```go
// Get clipboard history
type GetClipboardRequest struct {
    Limit int `json:"limit"`
}

type GetClipboardResponse struct {
    Entries []ClipboardEntry `json:"entries"`
}

// Clear clipboard history
type ClearClipboardResponse struct {
    Success bool `json:"success"`
}
```

### Handler Registration

```go
// In internal/core/ipc.go
func (s *IPCServer) registerClipboardHandlers() {
    s.RegisterHandler("clipboard:get", s.handleGetClipboard)
    s.RegisterHandler("clipboard:clear", s.handleClearClipboard)
}

func (s *IPCServer) handleGetClipboard(data []byte) ([]byte, error) {
    // Implementation
}
```

---

## Configuration

### Config Section

```toml
[launcher.clipboard]
# Maximum history entries
max_entries = 100

# Storage path (default: ~/.local/share/locus/clipboard.db)
storage_path = ""

# Auto-clear on startup
clear_on_startup = false

# Track images in clipboard
track_images = false
```

### Config Struct

```go
// In internal/config/config.go
type ClipboardConfig struct {
    MaxEntries      int    `toml:"max_entries"`
    StoragePath     string `toml:"storage_path"`
    ClearOnStartup  bool   `toml:"clear_on_startup"`
    TrackImages     bool   `toml:"track_images"`
}
```

---

## Migration from Python

### Python Implementation Analysis

**File**: `python_backup/launchers/clipboard_launcher.py`

**Key Mappings**:

| Python Concept | Go Implementation |
|----------------|-------------------|
| `subprocess.Popen(["wl-paste", "--watch"])` | `exec.Command("wl-paste", "--watch")` with goroutine |
| `json.load(history_file)` | SQLite database with `INSERT/SELECT` |
| `launcher_core.add_result()` | `launcher.AddResult(LauncherItem{...})` |
| Thread for watching clipboard | Goroutine with channel |

### Changes Required

- [ ] Python: file-based JSON → Go: SQLite with proper indexing
- [ ] Python: threading module → Go: goroutines + channels
- [ ] Python: dynamic entry dicts → Go: `ClipboardEntry` struct
- [ ] Python: GLib signals → Go: direct function calls (no GTK needed for background)

---

## Open Questions / Decisions Needed

1. **Clipboard Manager Compatibility**
   - Option A: Support only `wl-clipboard` (Wayland)
   - Option B: Add support for `xclip` (X11)
   - **Decision**: Option A (Wayland-only, matches project scope)

2. **Image Clipboard Support**
   - Option A: Implement now
   - Option B: Defer to future version
   - **Decision**: Option B (images marked as [NEEDS CLARIFICATION])

---

## Review Checklist

- [ ] All constitution articles reviewed
- [ ] Package structure defined
- [ ] Interfaces specified
- [ ] Test cases outlined
- [ ] IPC commands documented
- [ ] Configuration structure defined
- [ ] Migration notes complete