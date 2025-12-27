# Launcher Specification: file-launcher

**Type**: Launcher Implementation
**Feature ID**: 017
**Python Reference**: `python_backup/launchers/file_launcher.py`

---

## Launcher Definition

### Triggers
- Primary: `file`
- Aliases: `f`

### Purpose
Fast file search launcher with SQLite FTS5 full-text indexing, providing open, reveal, and copy path actions with smart file type icons and metadata display.

---

## User Stories

### US-001: Search Files Quickly (P1)
**Actor**: Power User
**Goal**: Find and open files rapidly across the filesystem
**Benefit**: Eliminates manual file browsing and directory navigation

**Independent Test**: Create test files, trigger launcher, verify files appear and can be opened

**Acceptance Scenarios**:
1. **Given** files exist in filesystem, **When** user types partial filename, **Then** matching files appear with metadata
2. **Given** file search results shown, **When** user selects file, **Then** file opens in default application
3. **Given** file selected, **When** user chooses "reveal" action, **Then** file manager opens at file location
4. **Given** file selected, **When** user chooses "copy path" action, **Then** full file path copied to clipboard

---

## Requirements

### Functional Requirements
- **FR-017-001**: System MUST use SQLite FTS5 for full-text file indexing
- **FR-017-002**: System MUST index home directory with smart exclusions (node_modules, .git, etc.)
- **FR-017-003**: System MUST provide real-time file search with ~50ms response time
- **FR-017-004**: System MUST support file opening with xdg-open
- **FR-017-005**: System MUST support file reveal in file manager (xdg-open on parent directory)
- **FR-017-006**: System MUST support copying file paths to clipboard
- **FR-017-007**: System MUST display file icons based on MIME type
- **FR-017-008**: System MUST show file size and formatted paths (relative to home)
- **FR-017-009**: System MUST handle indexing progress and status display
- **FR-017-010**: System MUST support tab completion for file paths

### Non-Functional Requirements
- **Performance**: Search results in <50ms for 100k+ files
- **Storage**: SQLite database with efficient indexing
- **Memory**: Minimal memory footprint during search
- **Indexing**: Background indexing without blocking UI
- **Error handling**: Graceful degradation if indexing fails

---

## Dependencies

### External Dependencies
- `xdg-open` - For opening files and directories
- SQLite with FTS5 support

### Internal Dependencies
- File indexer with SQLite FTS5 integration
- Icon manager for file type icons
- Clipboard utilities

---

## Success Criteria

- **SC-017-001**: File search completes within 50ms for indexed filesystem
- **SC-017-002**: All file actions (open, reveal, copy path) work correctly
- **SC-017-003**: File icons display correctly for different MIME types
- **SC-017-004**: Indexing completes successfully for home directory
- **SC-017-005**: Tab completion works for file paths

---

## Out of Scope
- Network file search
- Archive file content search
- File content preview
- Advanced file operations (move, copy, delete)

---

## Risks & Assumptions

### Risks
- SQLite FTS5 performance with very large file sets
- File permission issues during indexing
- Icon loading performance for many file types
- Memory usage during large indexing operations

### Assumptions
- User has read access to home directory
- SQLite with FTS5 is available
- xdg-open handles file opening correctly
- File manager supports directory opening

---

## Python Reference Analysis

**File**: `python_backup/launchers/file_launcher.py`

**Key Components to Port**:
1. `FileLauncher` class with indexer integration
2. `FileHook` class with action handling (open, reveal, copy_path)
3. `populate()` method with indexer status and search results
4. File type icon mapping and metadata display
5. SQLite FTS5 indexer integration

**Go Adaptation Notes**:
- Python: `get_file_indexer()` singleton → Go: file indexer package with interface
- Python: Action enums and dict data → Go: struct types with proper typing
- Python: MIME type to icon mapping → Go: icon manager with caching
- Python: File size formatting → Go: utility functions
- Python: Path formatting (~/ relative) → Go: path manipulation functions