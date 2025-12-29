package notification

import (
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/chess10kp/locus/internal/config"
	"github.com/godbus/dbus/v5"
	"github.com/gotk3/gotk3/glib"
)

type Daemon struct {
	conn         *dbus.Conn
	store        *Store
	queue        *Queue
	nextID       uint32
	activeNotifs map[uint32]string
	config       *config.NotificationConfig
	mu           sync.Mutex
	running      bool
}

func NewDaemon(store *Store, queue *Queue, cfg *config.NotificationConfig) *Daemon {
	return &Daemon{
		store:        store,
		queue:        queue,
		nextID:       1,
		activeNotifs: make(map[uint32]string),
		config:       cfg,
		running:      false,
	}
}

func (d *Daemon) Start() error {
	d.mu.Lock()
	defer d.mu.Unlock()

	if d.running {
		return fmt.Errorf("daemon already running")
	}

	conn, err := dbus.SessionBus()
	if err != nil {
		return fmt.Errorf("failed to connect to session bus: %w", err)
	}

	d.conn = conn

	if err := d.exportInterface(); err != nil {
		conn.Close()
		return fmt.Errorf("failed to export interface: %w", err)
	}

	reply, err := d.conn.RequestName("org.freedesktop.Notifications", dbus.NameFlagDoNotQueue)
	if err != nil {
		conn.Close()
		return fmt.Errorf("failed to request name: %w", err)
	}

	if reply != dbus.RequestNameReplyPrimaryOwner {
		conn.Close()
		return fmt.Errorf("name already owned by another process")
	}

	d.running = true

	log.Println("Notification daemon started on org.freedesktop.Notifications")

	return nil
}

func (d *Daemon) Stop() error {
	d.mu.Lock()
	defer d.mu.Unlock()

	if !d.running {
		return nil
	}

	d.running = false

	if d.conn != nil {
		d.conn.ReleaseName("org.freedesktop.Notifications")
		d.conn.Close()
		d.conn = nil
	}

	log.Println("Notification daemon stopped")

	return nil
}

func (d *Daemon) Notify(
	appName string,
	replacesID uint32,
	appIcon string,
	summary string,
	body string,
	actions []string,
	hints map[string]dbus.Variant,
	expireTimeout int32,
) (uint32, *dbus.Error) {
	log.Printf("Notify called: app=%s, summary=%s, body=%s", appName, summary, body)

	d.mu.Lock()
	defer d.mu.Unlock()

	if !d.running {
		log.Printf("Daemon not running, rejecting notification")
		return 0, dbus.MakeFailedError(fmt.Errorf("daemon not running"))
	}

	notifID := d.nextID
	d.nextID++

	urgency := UrgencyNormal
	if urgencyVariant, ok := hints["urgency"]; ok {
		if urgencyByte, ok := urgencyVariant.Value().(byte); ok {
			urgency = Urgency(urgencyByte)
			if urgency < UrgencyLow || urgency > UrgencyCritical {
				urgency = UrgencyNormal
			}
		}
	}

	timeout := int(expireTimeout)
	if timeout == -1 || urgency == UrgencyCritical {
		timeout = -1
	} else if timeout == 0 {
		timeout = 5000
	}

	actionList := make([]Action, 0)
	for i := 0; i < len(actions); i += 2 {
		if i+1 < len(actions) {
			actionList = append(actionList, Action{
				Key:   actions[i],
				Label: actions[i+1],
			})
		}
	}

	hintMap := make(map[string]string)
	for key, variant := range hints {
		if str, ok := variant.Value().(string); ok {
			hintMap[key] = str
		}
	}

	if replacesID > 0 {
		if oldNotifID, exists := d.activeNotifs[replacesID]; exists {
			d.store.RemoveNotification(oldNotifID)
			delete(d.activeNotifs, replacesID)
			d.queue.DismissBanner(oldNotifID)
		}
		notifID = replacesID
	}

	notificationID := generateID()
	log.Printf("Creating notification with ID: %s", notificationID)
	notif := &Notification{
		ID:            notificationID,
		AppName:       appName,
		AppIcon:       appIcon,
		Summary:       summary,
		Body:          body,
		Actions:       actionList,
		Hints:         hintMap,
		Timestamp:     time.Now(),
		ExpireTimeout: timeout,
		Urgency:       urgency,
		Read:          false,
		ReplacesID:    replacesID,
	}

	log.Printf("Adding notification to store...")
	if err := d.store.AddNotification(notif); err != nil {
		log.Printf("Failed to add notification to store: %v", err)
	} else {
		log.Printf("Successfully added notification to store")
	}

	d.activeNotifs[notifID] = notificationID
	log.Printf("Active notifications count: %d", len(d.activeNotifs))

	log.Printf("Queueing notification for display...")
	glib.IdleAdd(func() {
		log.Printf("Showing notification banner...")
		if err := d.queue.ShowNotification(notif); err != nil {
			log.Printf("Failed to show banner: %v", err)
		} else {
			log.Printf("Successfully showed notification banner")
		}
	})

	log.Printf("Returning notification ID: %d", notifID)
	return notifID, nil
}

func (d *Daemon) CloseNotification(id uint32) *dbus.Error {
	d.mu.Lock()
	defer d.mu.Unlock()

	if notifID, exists := d.activeNotifs[id]; exists {
		delete(d.activeNotifs, id)
		d.store.RemoveNotification(notifID)
		d.queue.DismissBanner(notifID)

		d.emitNotificationClosed(id, CloseReasonClosedByProgram)
	}

	return nil
}

func (d *Daemon) GetCapabilities() ([]string, *dbus.Error) {
	capabilities := []string{
		"actions",
		"body",
		"body-hyperlinks",
		"body-markup",
		"icon-static",
		"persistence",
		"sound",
	}
	return capabilities, nil
}

func (d *Daemon) GetServerInformation() (string, string, string, string, *dbus.Error) {
	return "Locus Notification Daemon", "Locus", "1.0", "1.2", nil
}

func (d *Daemon) exportInterface() error {
	return d.conn.Export(d, "/org/freedesktop/Notifications", "org.freedesktop.Notifications")
}

func (d *Daemon) emitNotificationClosed(id uint32, reason NotificationCloseReason) {
	if d.conn == nil {
		return
	}

	err := d.conn.Emit("/org/freedesktop/Notifications", "org.freedesktop.Notifications.NotificationClosed", id, uint32(reason))
	if err != nil {
		log.Printf("Failed to emit NotificationClosed signal: %v", err)
	}
}

func (d *Daemon) emitActionInvoked(id uint32, actionKey string) {
	if d.conn == nil {
		return
	}

	err := d.conn.Emit("/org/freedesktop/Notifications", "org.freedesktop.Notifications.ActionInvoked", id, actionKey)
	if err != nil {
		log.Printf("Failed to emit ActionInvoked signal: %v", err)
	}
}

func generateID() string {
	return fmt.Sprintf("notif-%d-%d", time.Now().UnixNano(), time.Now().Unix())
}
