# Launcher Specification: bookmark-launcher

**Type**: Launcher Implementation
**Feature ID**: 014
**Python Reference**: `python_backup/launchers/bookmark_launcher.py`

---

## Launcher Definition

### Triggers
- Primary: `bookmark`
- Aliases: `bm`, `bookmarks`

### Purpose
Browser bookmark management launcher that allows users to store, search, and open bookmarks, as well as add and remove bookmarks via commands.

---

## User Stories

### US-001: Browse and Open Bookmarks (P1)
**Actor**: Power User
**Goal**: Quickly access stored bookmarks
**Benefit**: Faster navigation to frequently used websites

**Independent Test**: Add bookmarks, trigger launcher, verify bookmarks appear and can be opened

**Acceptance Scenarios**:
1. **Given** user has stored bookmarks, **When** user types `>bookmark`, **Then** launcher shows all bookmarks
2. **Given** bookmarks displayed, **When** user types search query, **Then** results are filtered by URL content
3. **Given** bookmark selected, **When** user presses enter, **Then** bookmark opens in default browser

---

## Requirements

### Functional Requirements
- **FR-014-001**: System MUST store bookmarks in plain text file (`~/.bookmarks`)
- **FR-014-002**: System MUST display all bookmarks when no query provided
- **FR-014-003**: System MUST filter bookmarks by case-insensitive substring matching
- **FR-014-004**: System MUST open selected bookmarks using `xdg-open`
- **FR-014-005**: System MUST support adding bookmarks via `>bookmark add <url>` command
- **FR-014-006**: System MUST support removing bookmarks via `>bookmark remove <url>` command
- **FR-014-007**: System MUST support tab completion for existing bookmarks
- **FR-014-008**: System MUST show action buttons ("add", "replace") when no query provided

### Non-Functional Requirements
- **Performance**: Bookmark loading < 50ms for <1000 bookmarks
- **Storage**: Plain text file format (one URL per line)
- **Error handling**: Graceful fallback if `xdg-open` fails
- **Environment**: Clean environment variables for child processes (remove GTK/GDK vars)

---

## Dependencies

### External Dependencies
- `xdg-open` - For opening URLs in default browser

### Internal Dependencies
- Bookmark storage utilities (`get_bookmarks`, `add_bookmark`, `remove_bookmark`)

---

## Success Criteria

- **SC-014-001**: All stored bookmarks load and display correctly
- **SC-014-002**: Adding/removing bookmarks persists across sessions
- **SC-014-003**: URLs open in default browser without environment issues
- **SC-014-004**: Tab completion works for bookmark names

---

## Out of Scope
- Bookmark synchronization across devices
- Bookmark categorization/tagging
- Browser-specific bookmark import/export

---

## Risks & Assumptions

### Risks
- Environment variable cleaning might break some browser integrations
- Plain text storage provides no security for sensitive URLs

### Assumptions
- User has `xdg-open` available (standard on Linux)
- Default browser handles URL opening correctly
- `~/.bookmarks` file location is acceptable

---

## Python Reference Analysis

**File**: `python_backup/launchers/bookmark_launcher.py`

**Key Components to Port**:
1. `BookmarkHook` class - Handles bookmark selection, adding, removing, and URL opening
2. `populate()` method - Displays bookmarks and action buttons, handles filtering
3. `on_enter()` method - Command parsing for add/remove operations
4. `handle_tab()` method - Tab completion for bookmark names
5. Environment variable cleaning for child processes

**Go Adaptation Notes**:
- Python: `subprocess.Popen` with env cleaning → Go: `exec.Command` with environment setup
- Python: `utils.bookmarks` module → Go: `internal/bookmarks` package
- Python: Dynamic result objects → Go: `LauncherItem` struct with proper typing
- Python: GLib environment variable manipulation → Go: `os/exec` environment handling
- Need to handle both selection clicks and command-line operations