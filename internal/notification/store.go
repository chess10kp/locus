package notification

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type Store struct {
	notifications map[string]*Notification
	mu            sync.RWMutex
	maxHistory    int
	maxAgeDays    int
	persistPath   string
	eventChan     chan NotificationEvent
}

func NewStore(maxHistory, maxAgeDays int, persistPath string) (*Store, error) {
	s := &Store{
		notifications: make(map[string]*Notification),
		maxHistory:    maxHistory,
		maxAgeDays:    maxAgeDays,
		persistPath:   persistPath,
		eventChan:     make(chan NotificationEvent, 100),
	}

	if err := s.load(); err != nil {
		return nil, fmt.Errorf("failed to load notification history: %w", err)
	}

	s.cleanupExpired()

	return s, nil
}

func (s *Store) AddNotification(notif *Notification) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.notifications[notif.ID] = notif

	if len(s.notifications) > s.maxHistory {
		s.evictOldest()
	}

	s.emitEvent(NotificationEvent{
		Type:           "notification_added",
		NotificationID: notif.ID,
		UnreadCount:    s.getUnreadCountLocked(),
	})

	return nil
}

func (s *Store) RemoveNotification(id string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.notifications[id]; exists {
		delete(s.notifications, id)
		s.emitEvent(NotificationEvent{
			Type:           "notification_removed",
			NotificationID: id,
			UnreadCount:    s.getUnreadCountLocked(),
		})
		return true
	}
	return false
}

func (s *Store) MarkAsRead(id string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	if notif, exists := s.notifications[id]; exists {
		if !notif.Read {
			notif.Read = true
			s.emitEvent(NotificationEvent{
				Type:           "unread_count_changed",
				NotificationID: id,
				UnreadCount:    s.getUnreadCountLocked(),
			})
		}
		return true
	}
	return false
}

func (s *Store) MarkAllAsRead() int {
	s.mu.Lock()
	defer s.mu.Unlock()

	count := 0
	for _, notif := range s.notifications {
		if !notif.Read {
			notif.Read = true
			count++
		}
	}

	if count > 0 {
		s.emitEvent(NotificationEvent{
			Type:        "unread_count_changed",
			UnreadCount: s.getUnreadCountLocked(),
		})
	}

	return count
}

func (s *Store) ClearAll() int {
	s.mu.Lock()
	defer s.mu.Unlock()

	count := len(s.notifications)
	s.notifications = make(map[string]*Notification)

	s.emitEvent(NotificationEvent{
		Type:        "notifications_cleared",
		UnreadCount: 0,
	})

	return count
}

func (s *Store) GetNotifications(limit int) []*Notification {
	s.mu.RLock()
	defer s.mu.RUnlock()

	notifications := make([]*Notification, 0, len(s.notifications))
	for _, notif := range s.notifications {
		notifications = append(notifications, notif)
	}

	if limit > 0 && len(notifications) > limit {
		notifications = notifications[:limit]
	}

	return notifications
}

func (s *Store) GetUnreadNotifications() []*Notification {
	s.mu.RLock()
	defer s.mu.RUnlock()

	unread := make([]*Notification, 0)
	for _, notif := range s.notifications {
		if !notif.Read {
			unread = append(unread, notif)
		}
	}

	return unread
}

func (s *Store) GetNotificationsByApp(appName string) []*Notification {
	s.mu.RLock()
	defer s.mu.RUnlock()

	byApp := make([]*Notification, 0)
	for _, notif := range s.notifications {
		if notif.AppName == appName {
			byApp = append(byApp, notif)
		}
	}

	return byApp
}

func (s *Store) Search(query string) []*Notification {
	if query == "" {
		return []*Notification{}
	}

	queryLower := toLower(query)

	s.mu.RLock()
	defer s.mu.RUnlock()

	matches := make([]*Notification, 0)
	for _, notif := range s.notifications {
		if contains(toLower(notif.Summary), queryLower) ||
			contains(toLower(notif.Body), queryLower) ||
			contains(toLower(notif.AppName), queryLower) {
			matches = append(matches, notif)
		}
	}

	return matches
}

func (s *Store) GetUnreadCount() int {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.getUnreadCountLocked()
}

func (s *Store) getUnreadCountLocked() int {
	count := 0
	for _, notif := range s.notifications {
		if !notif.Read {
			count++
		}
	}
	return count
}

func (s *Store) Events() <-chan NotificationEvent {
	return s.eventChan
}

func (s *Store) Close() {
	close(s.eventChan)
	s.Save()
}

func (s *Store) Save() error {
	s.mu.RLock()
	defer s.mu.RUnlock()

	data := struct {
		Notifications []*Notification `json:"notifications"`
		Version       int             `json:"version"`
	}{
		Notifications: s.toSlice(),
		Version:       1,
	}

	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal notifications: %w", err)
	}

	if err := os.MkdirAll(filepath.Dir(s.persistPath), 0755); err != nil {
		return fmt.Errorf("failed to create cache directory: %w", err)
	}

	if err := os.WriteFile(s.persistPath, jsonData, 0644); err != nil {
		return fmt.Errorf("failed to write notification history: %w", err)
	}

	return nil
}

func (s *Store) load() error {
	if _, err := os.Stat(s.persistPath); os.IsNotExist(err) {
		return nil
	}

	data, err := os.ReadFile(s.persistPath)
	if err != nil {
		return fmt.Errorf("failed to read notification history: %w", err)
	}

	var loaded struct {
		Notifications []*Notification `json:"notifications"`
		Version       int             `json:"version"`
	}

	if err := json.Unmarshal(data, &loaded); err != nil {
		return fmt.Errorf("failed to unmarshal notifications: %w", err)
	}

	s.notifications = make(map[string]*Notification)
	for _, notif := range loaded.Notifications {
		s.notifications[notif.ID] = notif
	}

	return nil
}

func (s *Store) evictOldest() {
	if len(s.notifications) <= s.maxHistory {
		return
	}

	type timestampedNotif struct {
		id        string
		timestamp time.Time
	}

	notifs := make([]timestampedNotif, 0, len(s.notifications))
	for id, notif := range s.notifications {
		notifs = append(notifs, timestampedNotif{id: id, timestamp: notif.Timestamp})
	}

	for i := 0; i < len(notifs); i++ {
		for j := i + 1; j < len(notifs); j++ {
			if notifs[i].timestamp.After(notifs[j].timestamp) {
				notifs[i], notifs[j] = notifs[j], notifs[i]
			}
		}
	}

	oldestIDs := make([]string, 0)
	for i := 0; i < len(notifs)-s.maxHistory; i++ {
		oldestIDs = append(oldestIDs, notifs[i].id)
	}

	for _, id := range oldestIDs {
		delete(s.notifications, id)
	}
}

func (s *Store) cleanupExpired() int {
	s.mu.Lock()
	defer s.mu.Unlock()

	now := time.Now()
	cutoff := now.AddDate(0, 0, -s.maxAgeDays)

	removed := 0
	for id, notif := range s.notifications {
		if notif.Timestamp.Before(cutoff) {
			delete(s.notifications, id)
			removed++
		}
	}

	return removed
}

func (s *Store) toSlice() []*Notification {
	notifications := make([]*Notification, 0, len(s.notifications))
	for _, notif := range s.notifications {
		notifications = append(notifications, notif)
	}
	return notifications
}

func (s *Store) emitEvent(event NotificationEvent) {
	select {
	case s.eventChan <- event:
	default:
	}
}

func toLower(s string) string {
	result := make([]rune, len(s))
	for i, r := range s {
		if r >= 'A' && r <= 'Z' {
			result[i] = r + ('a' - 'A')
		} else {
			result[i] = r
		}
	}
	return string(result)
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && findSubstring(s, substr) >= 0
}

func findSubstring(s, substr string) int {
	for i := 0; i <= len(s)-len(substr); i++ {
		if matchAt(s, substr, i) {
			return i
		}
	}
	return -1
}

func matchAt(s, substr string, pos int) bool {
	for i := 0; i < len(substr); i++ {
		if s[pos+i] != substr[i] {
			return false
		}
	}
	return true
}
