# Implementation Tasks: Bookmark Launcher

**Feature ID**: 014
**Est. Total**: 12 hours

---

## Task Breakdown

### 014-01: Create Bookmark Storage Package
**Est**: 2 hrs | **Priority**: P1 | **Assignee**: TBD

**Description**:
Implement the bookmark storage utilities for reading/writing bookmarks to a file.

**Acceptance Criteria**:
- [ ] FileStorage struct with methods for GetAll, Add, Remove, Exists
- [ ] Proper error handling for file operations
- [ ] Support for default ~/.bookmarks file location
- [ ] Handle missing file gracefully

**Files to Modify**:
- `internal/bookmarks/bookmarks.go`

**Related Requirements**: FR-014-001, FR-014-002

**Status**: ⬜ Not Started

---

### 014-02: Implement Bookmark Launcher Core
**Est**: 3 hrs | **Priority**: P1 | **Assignee**: TBD

**Description**:
Create the main bookmark launcher with Populate, OnSelect, and OnEnter methods.

**Acceptance Criteria**:
- [ ] BookmarkLauncher implements LauncherInterface
- [ ] Registers with triggers: "bookmark", "bm", "bookmarks"
- [ ] Populate shows bookmarks and action buttons
- [ ] OnSelect opens bookmarks or handles remove mode
- [ ] OnEnter parses add/remove commands

**Files to Modify**:
- `internal/launcher/bookmark.go`

**Related Requirements**: FR-014-003, FR-014-004, FR-014-005, FR-014-006

**Status**: ⬜ Not Started

---

### 014-03: Add URL Opening Functionality
**Est**: 2 hrs | **Priority**: P1 | **Assignee**: TBD

**Description**:
Implement URL opening with environment variable cleaning for xdg-open.

**Acceptance Criteria**:
- [ ] openURL method uses exec.Command with xdg-open
- [ ] Environment variables cleaned (GTK, GDK, MALLOC, LD_PRELOAD)
- [ ] Process started in new session
- [ ] Error handling for missing xdg-open

**Files to Modify**:
- `internal/launcher/bookmark.go`

**Related Requirements**: FR-014-004

**Status**: ⬜ Not Started

---

### 014-04: Implement Tab Completion
**Est**: 1 hr | **Priority**: P2 | **Assignee**: TBD

**Description**:
Add tab completion support for bookmark names.

**Acceptance Criteria**:
- [ ] HandleTab method implemented
- [ ] Returns first matching bookmark for tab completion
- [ ] Case-insensitive matching

**Files to Modify**:
- `internal/launcher/bookmark.go`

**Related Requirements**: FR-014-007

**Status**: ⬜ Not Started

---

### 014-05: Add IPC Command Support
**Est**: 2 hrs | **Priority**: P2 | **Assignee**: TBD

**Description**:
Implement IPC commands for external bookmark management.

**Acceptance Criteria**:
- [ ] bookmark:add command adds bookmarks
- [ ] bookmark:remove command removes bookmarks
- [ ] Handlers registered in IPC server
- [ ] Proper request/response structures

**Files to Modify**:
- `internal/core/ipc.go`
- `internal/launcher/bookmark.go`

**Related Requirements**: FR-014-005, FR-014-006

**Status**: ⬜ Not Started

---

### 014-06: Add Configuration Support
**Est**: 1 hr | **Priority**: P2 | **Assignee**: TBD

**Description**:
Add configuration options for bookmark launcher.

**Acceptance Criteria**:
- [ ] BookmarkConfig struct in config.go
- [ ] TOML section [launcher.bookmark]
- [ ] bookmark_file setting with default
- [ ] Config used by launcher

**Files to Modify**:
- `internal/config/config.go`

**Related Requirements**: FR-014-001

**Status**: ⬜ Not Started

---

## Task Dependencies

```
014-01 → 014-02 → 014-03 → 014-04 → 014-05 → 014-06
```

---

## Testing Tasks

### 014-T1: Unit Tests for Bookmark Storage
**Est**: 1 hr

**Test Cases**:
- [ ] Add bookmark to file
- [ ] Remove bookmark from file
- [ ] Get all bookmarks
- [ ] Check bookmark exists
- [ ] Handle missing file

**Status**: ⬜ Not Started

### 014-T2: Unit Tests for Bookmark Launcher
**Est**: 1 hr

**Test Cases**:
- [ ] Test trigger recognition
- [ ] Test populate with bookmarks
- [ ] Test populate with filtering
- [ ] Test onEnter command parsing
- [ ] Test tab completion

**Status**: ⬜ Not Started

### 014-T3: Integration Tests
**Est**: 1 hr

**Test Cases**:
- [ ] Full bookmark workflow (add, search, open)
- [ ] IPC command handling
- [ ] File persistence across launcher restarts

**Status**: ⬜ Not Started

---

## Documentation Tasks

### 014-D1: Update Documentation
**Est**: 1 hr

- [ ] Update `GO_REWRITE_PROGRESS.md` with bookmark launcher completion
- [ ] Add launcher to README.md if needed
- [ ] Add inline code comments

**Status**: ⬜ Not Started

---

## Completion Checklist

- [ ] All tasks completed
- [ ] All tests passing
- [ ] Constitution compliance verified
- [ ] Documentation updated
- [ ] Code review approved