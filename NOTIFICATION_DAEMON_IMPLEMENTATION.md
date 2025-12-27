# Notifications Daemon Implementation

## Overview

The notifications daemon has been implemented for Locus as a complete, independent notification system that:

1. Runs within the main Locus application
2. Implements the freedesktop.org Notifications Specification
3. Displays banner windows using GTK layer shell
4. Persists notification history to disk
5. Communicates with the statusbar via IPC for unread count display
6. Supports notification actions (buttons on banners)
7. Continues working even if the statusbar crashes

## Components

### 1. Types (`internal/notification/types.go`)

Defines all notification-related data structures:
- `Notification`: Represents a desktop notification
- `Action`: Represents a notification action button
- `Urgency`: Enum for low/normal/critical urgency
- `Corner`: Enum for banner positioning (top-left, top-right, bottom-left, bottom-right)
- `NotificationCloseReason`: Reasons for notification closure
- `NotificationEvent`: Events emitted by the store
- `BannerPosition`: Position coordinates for banners

### 2. Store (`internal/notification/store.go`)

Thread-safe notification storage with:
- JSON persistence to `~/.cache/locus/notifications.json`
- Configurable max history (default: 500)
- Configurable max age days (default: 30)
- Query methods: recent, by app, unread, search
- Read/unread tracking with change notifications via channel
- Auto-cleanup of old notifications

Key methods:
- `AddNotification(notif)` - Add notification to store
- `RemoveNotification(id)` - Remove notification by ID
- `MarkAsRead(id)` - Mark as read
- `MarkAllAsRead()` - Mark all as read
- `ClearAll()` - Clear all notifications
- `GetNotifications(limit)` - Get recent notifications
- `GetUnreadNotifications()` - Get unread notifications
- `GetNotificationsByApp(appName)` - Get notifications from specific app
- `Search(query)` - Search notifications by text
- `GetUnreadCount()` - Get count of unread notifications
- `Events()` - Get event channel for store changes

### 3. Banner (`internal/notification/banner.go`)

GTK banner window implementation with:
- Layer shell overlay layer for positioning
- Slide-in/slide-out animations
- Urgency-based styling (green for low, yellow for normal, red for critical)
- Icon loading from theme or app
- Hover pauses auto-dismiss timer
- Click to dismiss
- Action button support
- Close button

Key methods:
- `NewBanner(notif, onClose, onAction)` - Create new banner
- `Show()` - Display banner
- `Dismiss()` - Dismiss banner with animation
- `UpdatePosition(x, y)` - Update banner position

### 4. Queue (`internal/notification/queue.go`)

Manages active banner windows:
- Maximum banners limit (default: 5)
- FIFO eviction when limit reached
- Configurable banner gaps and height
- Corner-based positioning
- Repositioning when banners appear/dismiss
- Callback support for close and action events

Key methods:
- `ShowNotification(notif)` - Add banner to queue
- `DismissBanner(id)` - Dismiss specific banner
- `DismissAll()` - Dismiss all banners
- `SetCorner(corner)` - Change positioning corner
- `GetActiveCount()` - Get number of active banners
- `Cleanup()` - Clean up all banners

### 5. Daemon (`internal/notification/daemon.go`)

D-Bus implementation of `org.freedesktop.Notifications`:
- `Notify(app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout)` - Receive notifications
- `CloseNotification(id)` - Close notification programmatically
- `GetCapabilities()` - Return supported features
- `GetServerInformation()` - Return server info (name, vendor, version, spec version)
- Signals: `NotificationClosed(id, reason)`, `ActionInvoked(id, action_key)`

Supported capabilities:
- actions
- body
- body-hyperlinks
- body-markup
- icon-static
- persistence
- sound

### 6. IPC Bridge (`internal/notification/ipc_bridge.go`)

Unix socket server for communication with statusbar and other components:
- Socket path: `~/.cache/locus/notifications.sock`
- JSON-based request/response protocol

Supported commands:
- `get_unread_count` - Get unread notification count
- `get_notifications` - Get notifications (with optional limit and app_name params)
- `search` - Search notifications (with query param)
- `mark_read` - Mark notification as read (with id param)
- `mark_all_read` - Mark all notifications as read
- `remove` - Remove notification (with id param)
- `clear_all` - Clear all notifications

Helper functions:
- `QueryNotificationStore(socketPath, command, params)` - Send request to daemon
- `QueryNotificationStoreSimple(socketPath, command)` - Send request without params
- `GetUnreadCount(socketPath)` - Helper to get unread count

### 7. Manager (`internal/notification/ipc_bridge.go`)

High-level manager that coordinates all components:
- Creates and initializes store, queue, daemon, IPC bridge
- Manages lifecycle (start/stop)
- Coordinates callbacks between components

Key methods:
- `NewManager(cfg)` - Create new manager
- `Start()` - Start all components
- `Stop()` - Stop all components
- `GetStore()` - Get notification store
- `GetQueue()` - Get banner queue
- `GetSocketPath()` - Get IPC socket path

### 8. Statusbar Module (`internal/statusbar/modules/notification.go`)

Updated statusbar notification module:
- Queries notification daemon via IPC for unread count
- Updates display every 5 seconds
- Configurable icon and format
- Click handler (currently placeholder)

## Integration

### Main Application (`internal/core/app.go`)

Updated to initialize and start the notification manager:
- Added `notificationMgr` field
- Created manager in `initialize()` if enabled in config
- Started manager automatically
- Stopped manager on application quit

### Configuration (`internal/config/config.go`)

Notification configuration already defined in config:

```toml
[notification]
[notification.daemon]
enabled = true
position = "top-right"
max_banners = 5
banner_gap = 10
banner_width = 400
banner_height = 100
animation_duration = 200

[notification.history]
max_history = 500
max_age_days = 30
persist_path = "~/.cache/locus/notifications.json"

[notification.timeouts]
low = 3000
normal = 5000
critical = -1
```

## Dependencies Added

- `github.com/godbus/dbus/v5` - D-Bus implementation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Locus Main App                      │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Statusbar    │  │  Launcher    │  │  IPC       │ │
│  │              │  │              │  │  Server    │ │
│  └──────┬───────┘  └──────────────┘  └────────────┘ │
│         │                                              │
│         │ Queries via IPC                               │
│         ▼                                              │
│  ┌────────────────────────────────────────────────────┐      │
│  │         Notification Manager                 │      │
│  │                                                 │      │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │      │
│  │  │  Store   │  │  Queue   │  │ IPC    │ │      │
│  │  │          │  │          │  │ Bridge │ │      │
│  │  └──────────┘  └────┬─────┘  └────────┘ │      │
│  │                       │                    │        │
│  │          ┌──────────┴────────────────────┘        │
│  │          │                                     │
│  │          ▼                                     │
│  │  ┌──────────────────────────┐                │
│  │  │   D-Bus Daemon       │                │
│  │  │                       │                │
│  │  │  org.freedesktop.     │                │
│  │  │  Notifications         │                │
│  │  └──────────┬───────────┘                │
│  └─────────────┼─────────────────────────────────┘
│                │ D-Bus
│                ▼
│       ┌────────────────┐
│       │  Sending     │
│       │  Apps       │
│       └────────────────┘
│                │
│         ┌─────┴─────┐
│         │           │
│         ▼           ▼
│   ┌────────┐  ┌────────┐
│   │ Banner │  │ Banner │
│   │ Windows│  │ Windows│
│   └────────┘  └────────┘
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Starting the Daemon

The daemon starts automatically when Locus is launched, if enabled in config:

```toml
[notification.daemon]
enabled = true
```

### Sending Notifications

Any application using the freedesktop.org notification spec will work:

```bash
# Example: notify-send
notify-send "Hello" "This is a notification"

# Example: with urgency
notify-send -u critical "Important" "Something critical happened"
```

### D-Bus API

```
Bus Name: org.freedesktop.Notifications
Object Path: /org/freedesktop/Notifications
Interface: org.freedesktop.Notifications
```

## Testing

To test the notification daemon:

1. Build and run locus:
```bash
go build ./cmd/locus
./locus
```

2. Send a test notification:
```bash
notify-send "Test" "This is a test notification"
```

3. Send notification with urgency:
```bash
notify-send -u critical "Critical" "This is critical!"
```

4. Send notification with action buttons (requires custom app):
```bash
# Some apps support actions, which will appear as buttons
```

## Configuration

### Banner Position
- `top-left` - Top left corner of screen
- `top-right` - Top right corner (default)
- `bottom-left` - Bottom left corner
- `bottom-right` - Bottom right corner

### Timeout Behavior
- Low urgency: 3 seconds (configurable)
- Normal urgency: 5 seconds (configurable)
- Critical urgency: No timeout (sticky until dismissed)
- App-specified timeout: Respected, unless critical urgency

## Notes

- The daemon runs as part of the main Locus process for simplicity
- If the main app crashes, notifications won't be received until restarted
- Notification history is persisted, so history is available across restarts
- The statusbar queries the daemon via IPC, so it stays in sync even after crashes
- Critical notifications are sticky and don't auto-dismiss
- Hovering over a banner pauses its auto-dismiss timer
