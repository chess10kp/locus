# Feature Specification: Clipboard Launcher

**Feature ID**: 015
**Status**: Draft
**Priority**: P1 (High)
**Python Reference**: `python_backup/launchers/clipboard_launcher.py`

---

## User Stories

### US-001: View Clipboard History (P1)
**Actor**: Power User
**Goal**: Quickly access previously copied items
**Benefit**: Saves time re-typing or re-copying content

**Independent Test**: Copy multiple items, trigger launcher, verify history appears

**Acceptance Scenarios**:
1. **Given** user has copied 5 items, **When** user triggers clipboard launcher, **Then** last 5 items appear in results
2. **Given** clipboard history shown, **When** user selects an item, **Then** that item is pasted to current window
3. **Given** clipboard launcher active, **When** user types search query, **Then** results are filtered by content

---

## Requirements

### Functional Requirements
- **FR-015-001**: System MUST track clipboard changes using clipboard manager (wl-paste on Wayland)
- **FR-015-002**: System MUST store at least 100 clipboard entries
- **FR-015-003**: System MUST display entries with preview (first 100 chars)
- **FR-015-004**: System MUST allow selecting and pasting clipboard entries
- **FR-015-005**: System MUST persist clipboard history across restarts
- **FR-015-006**: System MUST allow clearing clipboard history
- **FR-015-007**: [NEEDS CLARIFICATION: Should we support images in clipboard?]

### Non-Functional Requirements
- **Performance**: Clipboard detection < 100ms
- **Storage**: History file < 10MB for 1000 entries
- **Reliability**: Graceful degradation if clipboard manager not available

---

## Dependencies

### External Dependencies
- `wl-paste` - Wayland clipboard tool
- `wl-copy` - Wayland clipboard tool

### Internal Dependencies
- None (standalone launcher)

---

## Success Criteria

- **SC-015-001**: Clipboard changes detected within 100ms
- **SC-015-002**: History persists across application restarts
- **SC-015-003**: Search filters < 50ms for 1000 entries

---

## Out of Scope
- Clipboard syncing between devices
- Clipboard encryption
- Image clipboard handling (deferred to future)

---

## Risks & Assumptions

### Risks
- Wayland clipboard API complexity may require external tools
- Clipboard managers vary by compositor (Sway vs Hyprland)

### Assumptions
- User has wl-clipboard installed
- System uses Wayland

---

## Python Reference Analysis

**File**: `python_backup/launchers/clipboard_launcher.py`

**Key Components to Port**:
1. `ClipboardTracker` class - Monitors clipboard changes
2. `ClipboardHistory` - Stores and retrieves entries
3. `populate()` - Search and display history
4. `hook.on_select()` - Paste selected item

**Go Adaptation Notes**:
- Python: uses `subprocess.Popen` with `wl-paste --watch` → Go: use `exec.Command` with goroutine
- Python: JSON file storage → Go: SQLite with `INSERT/SELECT` (use SQLite for better performance)
- Python: GLib timeout for clipboard polling → Go: `time.Ticker` for periodic checks
- Need to handle both text and potential image clipboard content