# Lockscreen Implementation

This document describes the lockscreen implementation for Locus, which provides a secure screen lock mechanism similar to the Python implementation.

## Architecture

The lockscreen is implemented as a standalone component that:
- Works independently of the statusbar (can function even if statusbar fails)
- Uses GTK3 with gtk-layer-shell for proper Wayland/X11 support
- Supports multi-monitor setups (input on primary, read-only on others)
- Uses SHA256 password hashing for authentication (matching Python implementation)

## Components

### 1. LockScreenManager (`internal/lockscreen/lockscreen.go`)

Main lockscreen manager that:
- Creates lockscreen windows for all monitors
- Manages lock/unlock state
- Handles monitor reconfiguration
- Enforces maximum login attempts

### 2. LockScreenWindow (`internal/lockscreen/lockscreen.go`)

Individual lockscreen window that:
- Covers entire monitor with gtk-layer-shell overlay
- Shows password entry (input screen) or "Screen Locked" message (non-input)
- Blocks key combinations like Alt+Tab, Ctrl+Alt+F1-F12
- Prevents window closing
- Validates passwords against SHA256 hash

### 3. Configuration (`internal/config/config.go`)

Added `LockScreenConfig`:
```toml
[lock_screen]
password = "admin"          # Raw password (will be hashed)
password_hash = ""            # Pre-computed SHA256 hash
max_attempts = 3             # Maximum failed attempts before lockout
enabled = true                # Enable/disable lockscreen
```

### 4. Integration Points

**App (`internal/core/app.go`)**
- Added `lockscreen *lockscreen.LockScreenManager` field
- Added `ShowLockScreen()`, `HideLockScreen()`, `IsLocked()` methods
- Initializes lockscreen manager on startup
- Cleans up lockscreen on shutdown

**IPC (`internal/core/ipc.go`)**
- Added "lock" command handler
- Allows triggering lockscreen via `echo 'lock' | nc -U /tmp/locus_socket`

**Lock Launcher (`internal/launcher/lock.go`)**
- Updated to trigger lockscreen via IPC instead of swaylock
- Uses socket path from config

**Action Data (`internal/launcher/action_data.go`)**
- Added `LockScreenAction` type for future direct action support

**Styles (`internal/core/styles.go`)**
- Added CSS for lockscreen elements (`#lockscreen-window`, `#lockscreen-entry`, etc.)
- Matches existing Locus theme colors

## Security

### Authentication
- Uses SHA256 password hashing (matching Python implementation)
- Password hash can be pre-computed and stored (more secure than raw password)
- Falls back to raw password hashing at runtime if hash not provided

### Key Blocking
Prevents bypass attempts by blocking:
- Escape (clears password, doesn't unlock)
- Alt+Tab (window switching)
- Ctrl+Alt+F1-F12 (VT switching)

### Attempt Limiting
- Tracks failed authentication attempts
- Locks out after maximum attempts (default: 3)
- Requires re-authentication after lockout

## Multi-Monitor Support

- **Primary monitor (index 0)**: Shows password entry, accepts keyboard input
- **Secondary monitors**: Show "Screen Locked" message, keyboard mode exclusive
- **Monitor changes**: Automatically recreates lockscreens when display configuration changes

## Layer Shell Integration

Uses `internal/layer/shell.go` for:
- Fullscreen overlay (`LayerOverlay`)
- Exclusive keyboard access (`KeyboardModeExclusive`)
- All edges anchored for complete coverage
- Zero margins for edge-to-edge coverage

## Usage

### Via Launcher
1. Open launcher (default: Super+Space)
2. Type "lock" and press Enter
3. Lockscreen appears on all monitors

### Via IPC
```bash
echo 'lock' | nc -U /tmp/locus_socket
```

### Programmatic
```go
app.ShowLockScreen()
app.HideLockScreen()
app.IsLocked()
```

## Configuration

Add to `~/.config/locus/config.toml`:

```toml
[lock_screen]
password = "your-password"
max_attempts = 3
enabled = true
```

Or pre-compute hash for better security:
```bash
echo -n "your-password" | sha256sum
```

```toml
[lock_screen]
password_hash = "abc123..."
max_attempts = 3
enabled = true
```

## Design Decisions

### SHA256 vs PAM
- Python implementation uses SHA256, not PAM
- Keeps implementation simple and self-contained
- No external dependencies on PAM libraries
- Adequate for personal workstation locking

### Independence from Statusbar
- Lockscreen works even if statusbar crashes/fails
- Direct integration with App, not StatusBar
- Triggered via IPC for flexibility

### Lockscreen Timeout Behavior
After max attempts reached:
- Shows "Maximum attempts reached! Locking..."
- Waits 2 seconds
- Unlocks (allowing user to try again via another method if locked out)

## Testing

```bash
# Build
go build ./cmd/locus

# Run
./locus

# Test lockscreen
echo 'lock' | nc -U /tmp/locus_socket

# Unlock with configured password
# (Type password and press Enter)
```

## Future Enhancements

1. **PAM Authentication**: Add `github.com/msteinert/pam` for system authentication
2. **Biometric Support**: Integrate fingerprint readers
3. **Custom Background**: Allow setting lockscreen wallpaper
4. **Notifications**: Display lock status in notification history
5. **Lockscreen Timeout**: Auto-lock after inactivity period
