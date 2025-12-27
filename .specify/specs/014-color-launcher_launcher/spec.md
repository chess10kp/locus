# Launcher Specification: color-launcher

**Type**: Launcher Implementation
**Feature ID**: 022
**Python Reference**: `python_backup/launchers/color_launcher.py`

---

## Launcher Definition

### Triggers
- Primary: `color`
- Aliases: `cpicker`

### Purpose
Screen color picker launcher that captures colors from anywhere on screen using screenshot tools, maintains color history with visual swatches, and copies hex color values to clipboard.

---

## User Stories

### US-001: Pick Colors from Screen (P1)
**Actor**: Designer/Developer
**Goal**: Capture exact colors from UI elements or images
**Benefit**: Accurate color reproduction without manual color matching

**Independent Test**: Trigger color picker, click on screen area, verify hex color copies to clipboard

**Acceptance Scenarios**:
1. **Given** color launcher active, **When** user selects "Pick Color", **Then** screen capture mode activates
2. **Given** color picked from screen, **When** selection made, **Then** hex value copies to clipboard
3. **Given** color history exists, **When** launcher opens, **Then** recent colors display with swatches
4. **Given** color from history selected, **When** clicked, **Then** hex value copies to clipboard

---

## Requirements

### Functional Requirements
- **FR-022-001**: System MUST check for required tools (grim, slurp, convert, wl-copy) on startup
- **FR-022-002**: System MUST capture screen colors using grim + slurp screenshot region selection
- **FR-022-003**: System MUST parse color values from various formats (srgb, rgb, hex)
- **FR-022-004**: System MUST convert colors to standard hex format (#RRGGBB)
- **FR-022-005**: System MUST maintain color history with timestamps (max 10 colors)
- **FR-022-006**: System MUST persist color history to JSON cache file
- **FR-022-007**: System MUST display color swatches as visual previews
- **FR-022-008**: System MUST copy hex values to clipboard using appropriate tool
- **FR-022-009**: System MUST handle color picking cancellation gracefully

### Non-Functional Requirements
- **Performance**: Color parsing < 50ms, history loading < 100ms
- **Dependencies**: Requires Wayland screenshot tools (grim, slurp, ImageMagick)
- **Storage**: JSON cache file in ~/.cache/locus/color_history.json
- **Visual**: Color swatches with accurate color representation
- **Error handling**: Graceful degradation when tools unavailable

---

## Dependencies

### External Dependencies
- `grim` - Screenshot capture tool
- `slurp` - Region selection tool
- `convert` (ImageMagick) - Color extraction from images
- `wl-copy` or `xclip` - Clipboard utilities

### Internal Dependencies
- Pixbuf creation for color swatches
- JSON cache file management
- Screen capture utilities

---

## Success Criteria

- **SC-022-001**: Colors picked from screen are accurately captured and converted to hex
- **SC-022-002**: Color history persists across launcher sessions
- **SC-022-003**: Color swatches display correct colors
- **SC-022-004**: Hex values copy correctly to system clipboard
- **SC-022-005**: Error handling works when screenshot tools fail

---

## Out of Scope
- Color palette management or organization
- Color format conversion (HSL, HSV, etc.)
- Color comparison or similarity matching
- Integration with design tools

---

## Risks & Assumptions

### Risks
- Screenshot tool compatibility across Wayland compositors
- ImageMagick color extraction reliability
- Pixbuf performance for color swatch generation
- JSON cache file corruption handling

### Assumptions
- Wayland environment with grim/slurp available
- ImageMagick installed with convert command
- Clipboard tools available for the desktop environment

---

## Python Reference Analysis

**File**: `python_backup/launchers/color_launcher.py`

**Key Components to Port**:
1. `pick_color()` method - Screen capture pipeline using grim/slurp/convert
2. `_parse_color_to_hex()` method - Color format parsing and normalization
3. `_create_color_pixbuf()` method - Cairo-based color swatch generation
4. Color history management - JSON persistence with timestamp tracking
5. `copy_to_clipboard()` method - Cross-platform clipboard handling

**Go Adaptation Notes**:
- Python: `subprocess.run(["grim", ...])` → Go: `exec.Command("grim", ...)` with pipe handling
- Python: Cairo pixbuf creation → Go: GTK pixbuf or image generation
- Python: JSON cache with timestamps → Go: JSON marshaling with time tracking
- Python: Environment cleaning → Go: exec environment configuration
- Complex bash pipeline needs careful Go equivalent construction