package launcher

import (
	"encoding/json"
	"fmt"
	"time"
)

// ActionData represents data that can be executed when a launcher item is selected
type ActionData interface {
	Type() string
	ToJSON() ([]byte, error)
}

type ShellAction struct {
	Command string `json:"command"`
}

func (a *ShellAction) Type() string {
	return "shell"
}

func (a *ShellAction) ToJSON() ([]byte, error) {
	// Create a map with the type field included
	data := map[string]interface{}{
		"type":    a.Type(),
		"command": a.Command,
	}
	return json.Marshal(data)
}

// DesktopAction launches a desktop application
type DesktopAction struct {
	File string `json:"file"`
}

func (a *DesktopAction) Type() string {
	return "desktop"
}

func (a *DesktopAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type": a.Type(),
		"file": a.File,
	}
	return json.Marshal(data)
}

// ClipboardAction performs clipboard operations
type ClipboardAction struct {
	Text   string `json:"text"`
	Action string `json:"action"` // "copy", "paste", "clear", "history"
}

func (a *ClipboardAction) Type() string {
	return "clipboard"
}

func (a *ClipboardAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":   a.Type(),
		"text":   a.Text,
		"action": a.Action,
	}
	return json.Marshal(data)
}

// NotificationAction sends a notification
type NotificationAction struct {
	Title string `json:"title"`
	Body  string `json:"body"`
}

func (a *NotificationAction) Type() string {
	return "notification"
}

func (a *NotificationAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":  a.Type(),
		"title": a.Title,
		"body":  a.Body,
	}
	return json.Marshal(data)
}

// StatusMessageAction displays a status message in the status bar
type StatusMessageAction struct {
	Message  string        `json:"message"`
	Duration time.Duration `json:"duration,omitempty"` // 0 = default duration
}

func (a *StatusMessageAction) Type() string {
	return "status_message"
}

func (a *StatusMessageAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":     a.Type(),
		"message":  a.Message,
		"duration": a.Duration.String(),
	}
	return json.Marshal(data)
}

// RebuildLauncherAction forces a launcher to refresh its items
type RebuildLauncherAction struct {
	LauncherName string `json:"launcher_name"`
}

func (a *RebuildLauncherAction) Type() string {
	return "rebuild_launcher"
}

func (a *RebuildLauncherAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":          a.Type(),
		"launcher_name": a.LauncherName,
	}
	return json.Marshal(data)
}

// CustomAction allows user-defined action types
type CustomAction struct {
	DataType string      `json:"data_type"`
	Payload  interface{} `json:"payload"`
}

func (a *CustomAction) Type() string {
	return a.DataType
}

func (a *CustomAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":      a.Type(),
		"data_type": a.DataType,
		"payload":   a.Payload,
	}
	return json.Marshal(data)
}

// ParseActionData parses JSON data into the appropriate ActionData implementation
func ParseActionData(data []byte) (ActionData, error) {
	var raw map[string]interface{}
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("failed to unmarshal action data: %w", err)
	}

	actionType, ok := raw["type"].(string)
	if !ok {
		return nil, fmt.Errorf("action data missing type field")
	}

	switch actionType {
	case "shell":
		var action ShellAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse shell action: %w", err)
		}
		return &action, nil

	case "desktop":
		var action DesktopAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse desktop action: %w", err)
		}
		return &action, nil

	case "clipboard":
		var action ClipboardAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse clipboard action: %w", err)
		}
		return &action, nil

	case "notification":
		var action NotificationAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse notification action: %w", err)
		}
		return &action, nil

	case "status_message":
		var raw map[string]interface{}
		if err := json.Unmarshal(data, &raw); err != nil {
			return nil, fmt.Errorf("failed to parse status message action: %w", err)
		}

		action := &StatusMessageAction{
			Message: raw["message"].(string),
		}

		if durationStr, ok := raw["duration"].(string); ok {
			if duration, err := time.ParseDuration(durationStr); err == nil {
				action.Duration = duration
			}
		}

		return action, nil

	case "rebuild_launcher":
		var action RebuildLauncherAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse rebuild launcher action: %w", err)
		}
		return &action, nil

	case "music":
		var action MusicAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse music action: %w", err)
		}
		return &action, nil

	case "timer":
		var action TimerAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse timer action: %w", err)
		}
		return &action, nil

	case "lock_screen":
		fmt.Printf("trying to lokc the screen")
		var action LockScreenAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse lock screen action: %w", err)
		}
		return &action, nil

	case "window_focus":
		var action WindowFocusAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse window focus action: %w", err)
		}
		return &action, nil

	case "color":
		var action ColorAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse color action: %w", err)
		}
		return &action, nil

	default:
		// Treat as custom action
		var action CustomAction
		if err := json.Unmarshal(data, &action); err != nil {
			return nil, fmt.Errorf("failed to parse custom action: %w", err)
		}
		return &action, nil
	}
}

// NewShellAction creates a new ShellAction
func NewShellAction(command string) *ShellAction {
	return &ShellAction{Command: command}
}

// NewDesktopAction creates a new DesktopAction
func NewDesktopAction(file string) *DesktopAction {
	return &DesktopAction{File: file}
}

// NewClipboardAction creates a new ClipboardAction
func NewClipboardAction(text, action string) *ClipboardAction {
	return &ClipboardAction{Text: text, Action: action}
}

// NewNotificationAction creates a new NotificationAction
func NewNotificationAction(title, body string) *NotificationAction {
	return &NotificationAction{Title: title, Body: body}
}

// NewStatusMessageAction creates a new StatusMessageAction
func NewStatusMessageAction(message string, duration time.Duration) *StatusMessageAction {
	return &StatusMessageAction{Message: message, Duration: duration}
}

// NewRebuildLauncherAction creates a new RebuildLauncherAction
func NewRebuildLauncherAction(launcherName string) *RebuildLauncherAction {
	return &RebuildLauncherAction{LauncherName: launcherName}
}

// MusicAction performs music player operations
type MusicAction struct {
	Action string `json:"action"` // "toggle", "next", "prev", "clear", "play_file", "play_position", "view_queue", "view_library"
	Value  string `json:"value"`  // file path, position, etc.
}

func (a *MusicAction) Type() string {
	return "music"
}

func (a *MusicAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":   a.Type(),
		"action": a.Action,
		"value":  a.Value,
	}
	return json.Marshal(data)
}

// NewMusicAction creates a new MusicAction
func NewMusicAction(action, value string) *MusicAction {
	return &MusicAction{Action: action, Value: value}
}

// NewCustomAction creates a new CustomAction
func NewCustomAction(dataType string, payload interface{}) *CustomAction {
	return &CustomAction{DataType: dataType, Payload: payload}
}

// TimerAction performs timer operations
type TimerAction struct {
	Action string `json:"action"`
	Value  string `json:"value"`
}

func (a *TimerAction) Type() string {
	return "timer"
}

func (a *TimerAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":   a.Type(),
		"action": a.Action,
		"value":  a.Value,
	}
	return json.Marshal(data)
}

// NewTimerAction creates a new TimerAction
func NewTimerAction(action, value string) *TimerAction {
	return &TimerAction{Action: action, Value: value}
}

// LockScreenAction controls the lock screen
type LockScreenAction struct {
	Action string `json:"action"` // "show", "hide"
}

func (a *LockScreenAction) Type() string {
	return "lock_screen"
}

func (a *LockScreenAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":   a.Type(),
		"action": a.Action,
	}
	return json.Marshal(data)
}

// NewLockScreenAction creates a new LockScreenAction
func NewLockScreenAction(action string) *LockScreenAction {
	return &LockScreenAction{Action: action}
}

// WindowFocusAction focuses a specific window and switches to its workspace
type WindowFocusAction struct {
	ConID     int64  `json:"con_id"`    // Container ID for focusing
	Workspace string `json:"workspace"` // Workspace name
}

func (a *WindowFocusAction) Type() string {
	return "window_focus"
}

func (a *WindowFocusAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":      a.Type(),
		"con_id":    a.ConID,
		"workspace": a.Workspace,
	}
	return json.Marshal(data)
}

// NewWindowFocusAction creates a new WindowFocusAction
func NewWindowFocusAction(conID int64, workspace string) *WindowFocusAction {
	return &WindowFocusAction{
		ConID:     conID,
		Workspace: workspace,
	}
}

// ColorAction performs color picker operations
type ColorAction struct {
	Action string `json:"action"` // "save", "copy", "preview"
	Color  string `json:"color"`  // Color value in hex format
}

func (a *ColorAction) Type() string {
	return "color"
}

func (a *ColorAction) ToJSON() ([]byte, error) {
	data := map[string]interface{}{
		"type":   a.Type(),
		"action": a.Action,
		"color":  a.Color,
	}
	return json.Marshal(data)
}

// NewColorAction creates a new ColorAction
func NewColorAction(action, color string) *ColorAction {
	return &ColorAction{Action: action, Color: color}
}
