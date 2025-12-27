# Launcher Specification: emoji-launcher

**Type**: Launcher Implementation
**Feature ID**: 020
**Python Reference**: `python_backup/launchers/emoji_launcher.py`

---

## Launcher Definition

### Triggers
- Primary: `emoji`
- Aliases: `em`, `emj`, `e`

### Purpose
Emoji picker launcher that provides fast access to Unicode emojis with keyword-based search, displaying emojis in a clean interface and copying selected emojis to the system clipboard.

---

## User Stories

### US-001: Find and Insert Emojis (P1)
**Actor**: Content Creator
**Goal**: Quickly find and insert relevant emojis into text
**Benefit**: Enhanced communication without switching applications

**Independent Test**: Trigger emoji launcher, search for keyword, verify emoji copies to clipboard

**Acceptance Scenarios**:
1. **Given** emoji launcher active, **When** user types search term, **Then** matching emojis appear
2. **Given** emoji selected from results, **When** user presses enter, **Then** emoji copies to clipboard and launcher closes
3. **Given** no search query, **When** user triggers launcher, **Then** first 50 emojis display

---

## Requirements

### Functional Requirements
- **FR-020-001**: System MUST load emoji data from text file (emojis.txt) with format "emoji keywords..."
- **FR-020-002**: System MUST check for clipboard utilities (wl-copy or xclip) on startup
- **FR-020-003**: System MUST support keyword-based emoji search (case-insensitive)
- **FR-020-004**: System MUST display emojis as primary results without metadata
- **FR-020-005**: System MUST limit results to 50 items (9 with keyboard shortcuts)
- **FR-020-006**: System MUST copy selected emoji to system clipboard using appropriate tool
- **FR-020-007**: System MUST handle both Wayland (wl-copy) and X11 (xclip) environments

### Non-Functional Requirements
- **Performance**: Emoji loading < 100ms, search < 50ms for all emojis
- **Dependencies**: Requires clipboard utility (wl-copy or xclip)
- **File Format**: Plain text format with emoji + space + keywords per line
- **Unicode**: Full Unicode emoji support with proper encoding handling

---

## Dependencies

### External Dependencies
- `wl-copy` (Wayland) or `xclip` (X11) - Clipboard utilities

### Internal Dependencies
- Clipboard utility checking functions
- Emoji data file (emojis.txt) packaged with launcher

---

## Success Criteria

- **SC-020-001**: All emojis load correctly from data file
- **SC-020-002**: Keyword search finds relevant emojis accurately
- **SC-020-003**: Selected emojis copy to clipboard successfully
- **SC-020-004**: Works in both Wayland and X11 environments
- **SC-020-005**: Interface displays emojis clearly without metadata clutter

---

## Out of Scope
- Emoji categorization or filtering by category
- Custom emoji addition or management
- Emoji skin tone variations (handled by Unicode)
- Emoji history or favorites

---

## Risks & Assumptions

### Risks
- Clipboard utility availability varies by desktop environment
- Emoji rendering depends on system font support
- Unicode encoding issues with different terminals/editors
- Large emoji dataset may impact search performance

### Assumptions
- System has clipboard utilities installed (wl-copy or xclip)
- Terminal/editor supports Unicode emoji display
- User wants quick emoji insertion workflow

---

## Python Reference Analysis

**File**: `python_backup/launchers/emoji_launcher.py`

**Key Components to Port**:
1. `load_emoji_data()` method - Parses emojis.txt file into structured data
2. `search_emojis()` method - Keyword-based filtering with case-insensitive matching
3. `copy_to_clipboard()` method - Cross-platform clipboard handling (Wayland/X11)
4. `populate()` method - Clean display of emoji results without metadata
5. `check_dependencies()` - Clipboard utility detection

**Go Adaptation Notes**:
- Python: File reading with `open(encoding="utf-8")` → Go: `os.Open()` with proper UTF-8 handling
- Python: List comprehension for search → Go: slice filtering with `strings.Contains()`
- Python: subprocess.run with input → Go: `exec.Command().WithInput()` and environment handling
- Python: Dict emoji data → Go: struct slice with emoji and keywords fields
- Python: Exception handling → Go: error returns and validation