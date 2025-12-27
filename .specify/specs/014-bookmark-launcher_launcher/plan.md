# Implementation Plan: Bookmark Launcher

**Feature ID**: 014
**Go Version**: 1.23+
**Estimated Effort**: Medium

---

## Summary

Implement a bookmark launcher that allows users to store, search, and open browser bookmarks, with support for adding and removing bookmarks via commands.

---

## Constitution Compliance Check

- [x] **Article I**: Go best practices
  - Package naming: `bookmark`
  - Error handling: explicit returns for all I/O operations, fallback for missing `xdg-open`
  - Concurrency: synchronous operations (no concurrency needed)

- [x] **Article II**: Architecture principles
  - Clean architecture: `internal/launcher/bookmark.go`
  - Plugin registration: `registry.Register(bookmarkLauncher)`
  - IPC exposure: `bookmark:add`, `bookmark:remove` commands

- [x] **Article III**: Testing standards
  - Test coverage target: >80%
  - Test types: unit (bookmark operations), integration (IPC commands)

- [x] **Article IV**: Performance requirements
  - Response time: <50ms for bookmark loading
  - Resource limits: minimal memory usage

- [x] **Article V**: Configuration
  - Config section: `[launcher.bookmark]`
  - Default values: bookmark_file="~/.bookmarks"

---

## Architecture

### Package Structure

```
internal/
├── launcher/
│   ├── bookmark.go              # Main launcher implementation
│   └── bookmark_test.go         # Tests
├── bookmarks/                   # New package for bookmark utilities
│   ├── bookmarks.go             # Storage operations
│   └── bookmarks_test.go        # Tests
```

### Interface Definitions

```go
// BookmarkStorage manages bookmark persistence
type BookmarkStorage interface {
    GetAll() ([]string, error)
    Add(bookmark string) error
    Remove(bookmark string) error
    Exists(bookmark string) bool
}
```

### Data Flow

```
User Input → BookmarkLauncher.populate() → bookmarks.GetAll() → Filter results → Display
                                    ↓
                        Selection → exec.Command("xdg-open", url)
                                    ↓
                        Command parsing → bookmarks.Add()/Remove()
```

---

## Implementation Details

### Component 1: Bookmark Storage

**File**: `internal/bookmarks/bookmarks.go`

```go
package bookmarks

import (
    "bufio"
    "os"
    "path/filepath"
    "strings"
)

type FileStorage struct {
    filePath string
}

func NewFileStorage(filePath string) *FileStorage {
    if filePath == "" {
        home, _ := os.UserHomeDir()
        filePath = filepath.Join(home, ".bookmarks")
    }
    return &FileStorage{filePath: filePath}
}

func (fs *FileStorage) GetAll() ([]string, error) {
    file, err := os.Open(fs.filePath)
    if os.IsNotExist(err) {
        return []string{}, nil
    }
    if err != nil {
        return nil, err
    }
    defer file.Close()

    var bookmarks []string
    scanner := bufio.NewScanner(file)
    for scanner.Scan() {
        bookmark := strings.TrimSpace(scanner.Text())
        if bookmark != "" {
            bookmarks = append(bookmarks, bookmark)
        }
    }
    return bookmarks, scanner.Err()
}

func (fs *FileStorage) Add(bookmark string) error {
    bookmarks, err := fs.GetAll()
    if err != nil {
        return err
    }

    // Check if already exists
    for _, b := range bookmarks {
        if b == bookmark {
            return nil // Already exists
        }
    }

    file, err := os.OpenFile(fs.filePath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
    if err != nil {
        return err
    }
    defer file.Close()

    _, err = file.WriteString(bookmark + "\n")
    return err
}

func (fs *FileStorage) Remove(bookmark string) error {
    bookmarks, err := fs.GetAll()
    if err != nil {
        return err
    }

    // Filter out the bookmark to remove
    var filtered []string
    for _, b := range bookmarks {
        if b != bookmark {
            filtered = append(filtered, b)
        }
    }

    // Write back to file
    file, err := os.Create(fs.filePath)
    if err != nil {
        return err
    }
    defer file.Close()

    for _, b := range filtered {
        if _, err := file.WriteString(b + "\n"); err != nil {
            return err
        }
    }
    return nil
}

func (fs *FileStorage) Exists(bookmark string) bool {
    bookmarks, err := fs.GetAll()
    if err != nil {
        return false
    }
    for _, b := range bookmarks {
        if b == bookmark {
            return true
        }
    }
    return false
}
```

**Error Handling**: Return errors for file operations, handle missing file gracefully

**Concurrency Considerations**: No concurrency needed (file operations are atomic)

---

### Component 2: Bookmark Launcher

**File**: `internal/launcher/bookmark.go`

```go
package launcher

import (
    "os"
    "os/exec"
    "strings"

    "github.com/sigma/locus/internal/bookmarks"
    "github.com/sigma/locus/internal/core"
)

type BookmarkLauncher struct {
    storage *bookmarks.FileStorage
    removeMode bool
}

func NewBookmarkLauncher(main *core.Launcher) *BookmarkLauncher {
    storage := bookmarks.NewFileStorage("")
    l := &BookmarkLauncher{
        storage: storage,
    }
    core.LauncherRegistry.Register(l)
    return l
}

func (l *BookmarkLauncher) Name() string { return "bookmark" }

func (l *BookmarkLauncher) Triggers() []string {
    return []string{"bookmark", "bm", "bookmarks"}
}

func (l *BookmarkLauncher) Populate(query string, launcher *core.Launcher) error {
    bookmarks, err := l.storage.GetAll()
    if err != nil {
        return err
    }

    var items []string

    if l.removeMode {
        // In remove mode, show all bookmarks for selection
        items = bookmarks
    } else {
        if query == "remove" {
            // Enter remove mode
            l.removeMode = true
            items = bookmarks
        } else {
            // Filter bookmarks by query
            if query != "" {
                var filtered []string
                for _, b := range bookmarks {
                    if strings.Contains(strings.ToLower(b), strings.ToLower(query)) {
                        filtered = append(filtered, b)
                    }
                }
                bookmarks = filtered
            }
            // Add action buttons
            actions := []string{"add", "replace"}
            items = append(bookmarks, actions...)
        }
    }

    // Display results
    for i, item := range items {
        isBookmark := false
        for _, b := range bookmarks {
            if b == item {
                isBookmark = true
                break
            }
        }

        metadata := ""
        if isBookmark {
            metadata = "Bookmark"
        }

        launcher.AddResult(core.LauncherItem{
            Title:    item,
            Subtitle: metadata,
            Index:    i + 1,
            Data:     item,
        })

        if i >= 8 { // Limit results
            break
        }
    }

    return nil
}

func (l *BookmarkLauncher) OnSelect(item core.LauncherItem) error {
    data := item.Data.(string)

    if l.removeMode && l.storage.Exists(data) {
        // Remove bookmark
        l.removeMode = false
        return l.storage.Remove(data)
    } else if l.storage.Exists(data) {
        // Open bookmark
        return l.openURL(data)
    } else if data == "add" || data == "replace" {
        // Handle actions (could show dialog in future)
        return nil
    }

    return nil
}

func (l *BookmarkLauncher) OnEnter(text string) error {
    if !strings.HasPrefix(text, ">bookmark") {
        // Try to open as URL
        return l.openURL(text)
    }

    // Parse command
    command := strings.TrimSpace(text[len(">bookmark"):])
    if strings.HasPrefix(command, "add ") {
        url := strings.TrimSpace(command[4:])
        if url != "" {
            return l.storage.Add(url)
        }
    } else if strings.HasPrefix(command, "remove ") {
        url := strings.TrimSpace(command[7:])
        if url != "" {
            return l.storage.Remove(url)
        }
    } else {
        // Try to open as bookmark or URL
        if l.storage.Exists(command) {
            return l.openURL(command)
        } else {
            return l.openURL(command)
        }
    }

    return nil
}

func (l *BookmarkLauncher) HandleTab(query string) string {
    bookmarks, err := l.storage.GetAll()
    if err != nil {
        return ""
    }

    for _, b := range bookmarks {
        if strings.HasPrefix(strings.ToLower(b), strings.ToLower(query)) {
            return b
        }
    }
    return ""
}

func (l *BookmarkLauncher) GetSizeMode() (core.SizeMode, *core.Size) {
    return core.SizeModeDefault, nil
}

func (l *BookmarkLauncher) Cleanup() {
    // No cleanup needed
}

func (l *BookmarkLauncher) openURL(url string) error {
    // Clean environment like Python version
    env := os.Environ()
    // Remove GTK/GDK environment variables
    var cleanEnv []string
    for _, e := range env {
        if !strings.HasPrefix(e, "GTK_") && !strings.HasPrefix(e, "GDK_") &&
           !strings.HasPrefix(e, "MALLOC_PERTURB_") && e != "LD_PRELOAD" {
            cleanEnv = append(cleanEnv, e)
        }
    }

    cmd := exec.Command("xdg-open", url)
    cmd.Env = cleanEnv
    cmd.SysProcAttr = &syscall.SysProcAttr{
        Setsid: true, // Start in new session
    }
    return cmd.Start()
}
```

---

## Testing Strategy

### Unit Tests

**File**: `internal/bookmarks/bookmarks_test.go`

```go
func TestFileStorage(t *testing.T) {
    // Use temporary file
    tmpFile, err := os.CreateTemp("", "bookmarks_test")
    require.NoError(t, err)
    defer os.Remove(tmpFile.Name())

    storage := NewFileStorage(tmpFile.Name())

    // Test Add
    err = storage.Add("https://example.com")
    require.NoError(t, err)

    // Test GetAll
    bookmarks, err := storage.GetAll()
    require.NoError(t, err)
    assert.Contains(t, bookmarks, "https://example.com")

    // Test Exists
    assert.True(t, storage.Exists("https://example.com"))
    assert.False(t, storage.Exists("https://notfound.com"))

    // Test Remove
    err = storage.Remove("https://example.com")
    require.NoError(t, err)
    assert.False(t, storage.Exists("https://example.com"))
}
```

**File**: `internal/launcher/bookmark_test.go`

```go
func TestBookmarkLauncherTriggers(t *testing.T) {
    launcher := NewBookmarkLauncher(nil)
    assert.Equal(t, "bookmark", launcher.Name())
    assert.Contains(t, launcher.Triggers(), "bm")
}

func TestBookmarkLauncherPopulate(t *testing.T) {
    launcher := NewBookmarkLauncher(nil)

    // Mock storage would be needed for full testing
    // This is simplified for illustration
    err := launcher.Populate("", nil)
    assert.NoError(t, err)
}
```

### Integration Tests

Test IPC commands and full workflow with temporary files.

---

## IPC Integration

### Commands

```go
// Add bookmark
type AddBookmarkRequest struct {
    URL string `json:"url"`
}

type AddBookmarkResponse struct {
    Success bool `json:"success"`
}

// Remove bookmark
type RemoveBookmarkRequest struct {
    URL string `json:"url"`
}

type RemoveBookmarkResponse struct {
    Success bool `json:"success"`
}
```

### Handler Registration

```go
// In internal/core/ipc.go
func (s *IPCServer) registerBookmarkHandlers() {
    s.RegisterHandler("bookmark:add", s.handleAddBookmark)
    s.RegisterHandler("bookmark:remove", s.handleRemoveBookmark)
}
```

---

## Configuration

### Config Section

```toml
[launcher.bookmark]
# Path to bookmarks file (default: ~/.bookmarks)
bookmark_file = "~/.bookmarks"
```

### Config Struct

```go
// In internal/config/config.go
type BookmarkConfig struct {
    BookmarkFile string `toml:"bookmark_file"`
}
```

---

## Migration from Python

### Python Implementation Analysis

**File**: `python_backup/launchers/bookmark_launcher.py`

**Key Mappings**:

| Python Concept | Go Implementation |
|----------------|-------------------|
| `utils.get_bookmarks()` | `bookmarks.FileStorage.GetAll()` |
| `utils.add_bookmark(url)` | `bookmarks.FileStorage.Add(url)` |
| `utils.remove_bookmark(url)` | `bookmarks.FileStorage.Remove(url)` |
| `subprocess.Popen(["xdg-open", url], env=env)` | `exec.Command("xdg-open", url).WithEnv(cleanEnv)` |
| `launcher_core.add_launcher_result()` | `launcher.AddResult(LauncherItem{...})` |
| `BookmarkHook` class with methods | `BookmarkLauncher` with interface methods |

### Changes Required

- [ ] Python: file operations with context managers → Go: explicit file open/close with defer
- [ ] Python: dynamic environment manipulation → Go: slice filtering for clean environment
- [ ] Python: string operations → Go: `strings` package functions
- [ ] Python: exception handling → Go: error returns
- [ ] Python: class-based hooks → Go: interface methods on launcher struct

---

## Open Questions / Decisions Needed

1. **Bookmark File Location**
   - Option A: `~/.bookmarks` (matches Python)
   - Option B: `~/.config/locus/bookmarks` (XDG compliant)
   - **Decision**: Option A (maintains compatibility with existing Python users)

2. **Environment Variable Cleaning**
   - Option A: Remove GTK/GDK/MALLOC/LD_PRELOAD (matches Python)
   - Option B: Keep all environment variables
   - **Decision**: Option A (prevents child process crashes)

---

## Review Checklist

- [ ] All constitution articles reviewed
- [ ] Package structure defined
- [ ] Interfaces specified
- [ ] Test cases outlined
- [ ] IPC commands documented
- [ ] Configuration structure defined
- [ ] Migration notes complete