package launcher

import (
	"encoding/json"
	"testing"
	"time"
)

func TestShellAction(t *testing.T) {
	action := NewShellAction("ls -la")

	if action.Type() != "shell" {
		t.Errorf("Expected type 'shell', got '%s'", action.Type())
	}

	if action.Command != "ls -la" {
		t.Errorf("Expected command 'ls -la', got '%s'", action.Command)
	}

	data, err := action.ToJSON()
	if err != nil {
		t.Fatalf("Failed to marshal to JSON: %v", err)
	}

	var raw map[string]interface{}
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatalf("Failed to unmarshal JSON: %v", err)
	}

	if raw["command"] != "ls -la" {
		t.Errorf("Expected command in JSON to be 'ls -la', got '%v'", raw["command"])
	}
}

func TestClipboardAction(t *testing.T) {
	action := NewClipboardAction("hello world", "copy")

	if action.Type() != "clipboard" {
		t.Errorf("Expected type 'clipboard', got '%s'", action.Type())
	}

	if action.Text != "hello world" {
		t.Errorf("Expected text 'hello world', got '%s'", action.Text)
	}

	if action.Action != "copy" {
		t.Errorf("Expected action 'copy', got '%s'", action.Action)
	}
}

func TestNotificationAction(t *testing.T) {
	action := NewNotificationAction("Title", "Body")

	if action.Type() != "notification" {
		t.Errorf("Expected type 'notification', got '%s'", action.Type())
	}

	if action.Title != "Title" {
		t.Errorf("Expected title 'Title', got '%s'", action.Title)
	}

	if action.Body != "Body" {
		t.Errorf("Expected body 'Body', got '%s'", action.Body)
	}
}

func TestStatusMessageAction(t *testing.T) {
	duration := 5 * time.Second
	action := NewStatusMessageAction("Status message", duration)

	if action.Type() != "status_message" {
		t.Errorf("Expected type 'status_message', got '%s'", action.Type())
	}

	if action.Message != "Status message" {
		t.Errorf("Expected message 'Status message', got '%s'", action.Message)
	}

	if action.Duration != duration {
		t.Errorf("Expected duration %v, got %v", duration, action.Duration)
	}
}

func TestRebuildLauncherAction(t *testing.T) {
	action := NewRebuildLauncherAction("timer")

	if action.Type() != "rebuild_launcher" {
		t.Errorf("Expected type 'rebuild_launcher', got '%s'", action.Type())
	}

	if action.LauncherName != "timer" {
		t.Errorf("Expected launcher name 'timer', got '%s'", action.LauncherName)
	}
}

func TestCustomAction(t *testing.T) {
	payload := map[string]interface{}{"key": "value"}
	action := NewCustomAction("mytype", payload)

	if action.Type() != "mytype" {
		t.Errorf("Expected type 'mytype', got '%s'", action.Type())
	}

	if action.DataType != "mytype" {
		t.Errorf("Expected data type 'mytype', got '%s'", action.DataType)
	}
}

func TestParseActionData(t *testing.T) {
	testCases := []struct {
		name        string
		action      ActionData
		expectError bool
	}{
		{
			name:   "shell action",
			action: NewShellAction("echo hello"),
		},
		{
			name:   "clipboard action",
			action: NewClipboardAction("text", "copy"),
		},
		{
			name:   "notification action",
			action: NewNotificationAction("Title", "Body"),
		},
		{
			name:   "status message action",
			action: NewStatusMessageAction("Message", time.Second),
		},
		{
			name:   "rebuild launcher action",
			action: NewRebuildLauncherAction("timer"),
		},
		{
			name:   "custom action",
			action: NewCustomAction("mytype", "payload"),
		},
		{
			name:        "invalid json",
			action:      nil,
			expectError: true,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			var data []byte
			var err error

			if tc.action != nil {
				data, err = tc.action.ToJSON()
				if err != nil {
					t.Fatalf("Failed to marshal action: %v", err)
				}
			} else {
				data = []byte(`invalid json`)
			}

			parsed, err := ParseActionData(data)

			if tc.expectError {
				if err == nil {
					t.Error("Expected error but got none")
				}
				return
			}

			if err != nil {
				t.Fatalf("Unexpected error: %v", err)
			}

			if parsed.Type() != tc.action.Type() {
				t.Errorf("Expected type '%s', got '%s'", tc.action.Type(), parsed.Type())
			}
		})
	}
}

func TestParseActionDataMissingType(t *testing.T) {
	data := []byte(`{"command": "ls"}`)
	_, err := ParseActionData(data)
	if err == nil {
		t.Error("Expected error for missing type field, got none")
	}
}

func TestParseActionDataInvalidJSON(t *testing.T) {
	data := []byte(`{invalid json}`)
	_, err := ParseActionData(data)
	if err == nil {
		t.Error("Expected error for invalid JSON, got none")
	}
}
