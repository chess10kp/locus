package notification

import "time"

type Urgency int

const (
	UrgencyLow Urgency = iota
	UrgencyNormal
	UrgencyCritical
)

func (u Urgency) String() string {
	switch u {
	case UrgencyLow:
		return "low"
	case UrgencyNormal:
		return "normal"
	case UrgencyCritical:
		return "critical"
	default:
		return "normal"
	}
}

type Corner string

const (
	CornerTopLeft     Corner = "top-left"
	CornerTopRight    Corner = "top-right"
	CornerBottomLeft  Corner = "bottom-left"
	CornerBottomRight Corner = "bottom-right"
)

type Notification struct {
	ID            string            `json:"id"`
	AppName       string            `json:"app_name"`
	AppIcon       string            `json:"app_icon"`
	Summary       string            `json:"summary"`
	Body          string            `json:"body"`
	Actions       []Action          `json:"actions"`
	Hints         map[string]string `json:"hints"`
	Timestamp     time.Time         `json:"timestamp"`
	ExpireTimeout int               `json:"expire_timeout"` // milliseconds, -1 for never
	Urgency       Urgency           `json:"urgency"`
	Read          bool              `json:"read"`
	ReplacesID    uint32            `json:"replaces_id,omitempty"`
}

type Action struct {
	Key     string `json:"key"`
	Label   string `json:"label"`
	Invoked bool   `json:"invoked"`
}

type NotificationCloseReason int

const (
	CloseReasonExpired         NotificationCloseReason = 1
	CloseReasonDismissed       NotificationCloseReason = 2
	CloseReasonClosedByProgram NotificationCloseReason = 3
	CloseReasonUndefined       NotificationCloseReason = 4
)

type NotificationEvent struct {
	Type           string `json:"type"`
	NotificationID string `json:"notification_id"`
	UnreadCount    int    `json:"unread_count"`
}

type BannerPosition struct {
	Corner Corner
	X      int
	Y      int
	Width  int
	Height int
}
