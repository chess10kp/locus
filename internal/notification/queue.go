package notification

import (
	"log"
	"sync"
)

type Queue struct {
	store        *Store
	banners      map[string]*Banner
	maxBanners   int
	bannerGap    int
	bannerHeight int
	corner       Corner
	mu           sync.RWMutex
	onClose      func(string)
	onAction     func(string, string)
}

func NewQueue(store *Store, maxBanners, bannerGap, bannerHeight int, corner Corner) *Queue {
	return &Queue{
		store:        store,
		banners:      make(map[string]*Banner),
		maxBanners:   maxBanners,
		bannerGap:    bannerGap,
		bannerHeight: bannerHeight,
		corner:       corner,
	}
}

func (q *Queue) SetCallbacks(onClose func(string), onAction func(string, string)) {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.onClose = onClose
	q.onAction = onAction
}

func (q *Queue) ShowNotification(notif *Notification) error {
	q.mu.Lock()
	defer q.mu.Unlock()

	if _, exists := q.banners[notif.ID]; exists {
		return nil
	}

	if len(q.banners) >= q.maxBanners {
		q.removeOldestBanner()
	}

	banner, err := NewBanner(notif, q.onBannerClose, q.onBannerAction)
	if err != nil {
		return err
	}

	q.banners[notif.ID] = banner
	banner.Show()

	q.repositionAllBanners()

	return nil
}

func (q *Queue) removeOldestBanner() {
	if len(q.banners) == 0 {
		return
	}

	oldestID := ""
	oldestTime := q.banners[q.getFirstKey()].notification.Timestamp

	for id, banner := range q.banners {
		if banner.notification.Timestamp.Before(oldestTime) {
			oldestTime = banner.notification.Timestamp
			oldestID = id
		}
	}

	if oldestID != "" {
		q.dismissBanner(oldestID)
	}
}

func (q *Queue) getFirstKey() string {
	for k := range q.banners {
		return k
	}
	return ""
}

func (q *Queue) DismissBanner(id string) {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.dismissBanner(id)
}

func (q *Queue) dismissBanner(id string) {
	if banner, exists := q.banners[id]; exists {
		delete(q.banners, id)
		banner.Dismiss()
		q.repositionAllBanners()
	}
}

func (q *Queue) DismissAll() {
	q.mu.Lock()
	defer q.mu.Unlock()

	for id, banner := range q.banners {
		banner.Dismiss()
		delete(q.banners, id)
	}
}

func (q *Queue) SetCorner(corner Corner) {
	q.mu.Lock()
	q.corner = corner
	q.mu.Unlock()

	q.repositionAllBanners()
}

func (q *Queue) GetActiveCount() int {
	q.mu.RLock()
	defer q.mu.RUnlock()
	return len(q.banners)
}

func (q *Queue) onBannerClose(id string) {
	q.mu.Lock()
	defer q.mu.Unlock()

	if _, exists := q.banners[id]; exists {
		delete(q.banners, id)
		q.repositionAllBanners()
	}

	if q.onClose != nil {
		q.onClose(id)
	}
}

func (q *Queue) onBannerAction(notifID, actionKey string) {
	q.mu.Lock()
	banner, exists := q.banners[notifID]
	q.mu.Unlock()

	if !exists {
		return
	}

	notif := banner.notification
	for i, action := range notif.Actions {
		if action.Key == actionKey {
			notif.Actions[i].Invoked = true
			break
		}
	}

	q.store.MarkAsRead(notifID)

	if q.onAction != nil {
		q.onAction(notifID, actionKey)
	}
}

func (q *Queue) repositionAllBanners() {
	q.mu.Lock()
	defer q.mu.Unlock()

	banners := make([]*Banner, 0, len(q.banners))
	for _, banner := range q.banners {
		banners = append(banners, banner)
	}

	for i, banner := range banners {
		q.positionBanner(banner, i)
	}
}

func (q *Queue) positionBanner(banner *Banner, index int) {
	x, y := q.calculatePosition(index)
	banner.UpdatePosition(x, y)
}

func (q *Queue) calculatePosition(index int) (int, int) {
	switch q.corner {
	case CornerTopLeft:
		return 10, 40 + (index * (q.bannerHeight + q.bannerGap))
	case CornerTopRight:
		return 10, 40 + (index * (q.bannerHeight + q.bannerGap))
	case CornerBottomLeft:
		return 10, -10 - (index * (q.bannerHeight + q.bannerGap))
	case CornerBottomRight:
		return 10, -10 - (index * (q.bannerHeight + q.bannerGap))
	default:
		return 10, 40 + (index * (q.bannerHeight + q.bannerGap))
	}
}

func (q *Queue) Cleanup() {
	q.mu.Lock()
	defer q.mu.Unlock()

	for _, banner := range q.banners {
		banner.Dismiss()
	}

	q.banners = make(map[string]*Banner)

	log.Println("Notification queue cleaned up")
}
