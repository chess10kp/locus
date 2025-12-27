# Launcher Specification: music-launcher

**Type**: Launcher Implementation
**Feature ID**: 019
**Python Reference**: `python_backup/launchers/music_launcher.py`

---

## Launcher Definition

### Triggers
- Primary: `mpd`
- Aliases: `music`, `m`

### Purpose
Music Player Daemon (MPD) client launcher that provides music library browsing, queue management, and playback controls with seamless integration between local file browsing and MPD playlist management.

---

## User Stories

### US-001: Browse and Play Music Library (P1)
**Actor**: Music Enthusiast
**Goal**: Browse personal music collection and play tracks
**Benefit**: Quick access to music library without leaving workflow

**Independent Test**: Add music files, trigger launcher, verify library appears and playback works

**Acceptance Scenarios**:
1. **Given** music files exist, **When** user types `>mpd`, **Then** music library displays with search
2. **Given** track selected from library, **When** user presses enter, **Then** track begins playing
3. **Given** currently playing, **When** user selects play/pause control, **Then** playback toggles
4. **Given** queue view active, **When** user selects track position, **Then** playback jumps to that position

---

## Requirements

### Functional Requirements
- **FR-019-001**: System MUST check for mpc (MPD client) availability on startup
- **FR-019-002**: System MUST scan local music directory for supported audio files (.mp3, .flac, .opus, .ogg, .m4a, .wav)
- **FR-019-003**: System MUST display current MPD status (playing/paused/stopped) with current song info
- **FR-019-004**: System MUST provide playback controls (play/pause/next/prev/clear/toggle)
- **FR-019-005**: System MUST support two main views: library (browse files) and queue (current playlist)
- **FR-019-006**: System MUST allow adding tracks from library to MPD queue
- **FR-019-007**: System MUST allow playing specific positions from queue
- **FR-019-008**: System MUST allow removing tracks from queue
- **FR-019-009**: System MUST support switching between library and queue views
- **FR-019-010**: System MUST cache file scan results to avoid repeated directory traversal

### Non-Functional Requirements
- **Performance**: File scanning < 30 seconds for 10k files, status queries < 200ms
- **Dependencies**: Requires mpc and running MPD daemon
- **Threading**: Background file scanning without blocking UI
- **Caching**: Scan cache persists until manual refresh
- **Formats**: Support for MP3, FLAC, Opus, OGG, M4A, WAV files

---

## Dependencies

### External Dependencies
- `mpc` - Music Player Daemon command-line client
- Running MPD daemon instance

### Internal Dependencies
- Music directory configuration (MUSIC_DIR)
- File scanning utilities
- MPD command execution helpers

---

## Success Criteria

- **SC-019-001**: Music library scans successfully and displays audio files
- **SC-019-002**: Playback controls work for all MPD states
- **SC-019-003**: Queue management allows adding/removing tracks
- **SC-019-004**: Switching between library and queue views works seamlessly
- **SC-019-005**: Status display shows accurate current song and playback state

---

## Out of Scope
- MPD server configuration or management
- Audio file transcoding or conversion
- Playlist file management (.m3u, .pls)
- Advanced MPD features (crossfade, replaygain)
- Music metadata editing or display

---

## Risks & Assumptions

### Risks
- MPD daemon not running or misconfigured
- Large music libraries causing slow startup scans
- mpc command variations across distributions
- File permission issues in music directory

### Assumptions
- MPD is properly configured and running
- User has read access to music directory
- mpc commands are stable and available
- Music files are properly tagged (though not required)

---

## Python Reference Analysis

**File**: `python_backup/launchers/music_launcher.py`

**Key Components to Port**:
1. `MpdHook` class - Handles all user interactions and view switching
2. `populate()` method - Dual-mode display (library vs queue)
3. `_scan_worker()` method - Background file system scanning
4. `get_status()` method - MPD status parsing and state management
5. Control methods (play_file, play_position, control, etc.)

**Go Adaptation Notes**:
- Python: `subprocess.run(["mpc", ...])` → Go: `exec.Command("mpc", ...)` with output parsing
- Python: Threading for background scanning → Go: goroutines for concurrent file scanning
- Python: Dict status parsing → Go: struct types for MPD status
- Python: Dynamic view switching → Go: query-based mode detection ("queue" prefix)
- Python: List caching → Go: slice caching with mutex protection