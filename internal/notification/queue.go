package notification

import (
	"log"
	"sync"

	"github.com/chess10kp/locus/internal/launcher"
)

type Queue struct {
	store             *Store
	banners           map[string]*Banner
	maxBanners        int
	bannerGap         int
	bannerHeight      int
	bannerWidth       int
	animationDuration int
	corner            Corner
	iconCache         *launcher.IconCache
	mu                sync.RWMutex
	onClose           func(string)
	onAction          func(string, string)
}

func NewQueue(store *Store, maxBanners, bannerGap, bannerHeight, bannerWidth, animationDuration int, corner Corner, iconCache *launcher.IconCache) *Queue {
	return &Queue{
		store:             store,
		banners:           make(map[string]*Banner),
		maxBanners:        maxBanners,
		bannerGap:         bannerGap,
		bannerHeight:      bannerHeight,
		bannerWidth:       bannerWidth,
		animationDuration: animationDuration,
		corner:            corner,
		iconCache:         iconCache,
	}
}

func (q *Queue) SetCallbacks(onClose func(string), onAction func(string, string)) {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.onClose = onClose
	q.onAction = onAction
}

func (q *Queue) ShowNotification(notif *Notification) error {
	log.Printf("Queue.ShowNotification called for: %s", notif.Summary)
	q.mu.Lock()
	defer q.mu.Unlock()

	if _, exists := q.banners[notif.ID]; exists {
		log.Printf("Banner already exists for notification: %s", notif.ID)
		return nil
	}

	if len(q.banners) >= q.maxBanners {
		log.Printf("Max banners reached, removing oldest...")
		q.removeOldestBanner()
	}

	log.Printf("Creating new banner...")
	banner, err := NewBanner(notif, q.onBannerClose, q.onBannerAction, q.bannerWidth, q.bannerHeight, q.animationDuration, q.iconCache)
	if err != nil {
		log.Printf("Failed to create banner: %v", err)
		return err
	}
	log.Printf("Banner created successfully")

	q.banners[notif.ID] = banner
	log.Printf("Calling banner.Show()...")
	banner.Show()
	log.Printf("Banner.Show() completed")

	log.Printf("Repositioning all banners...")
	q.repositionAllBanners()
	log.Printf("Banner repositioning complete")

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
	position := q.calculatePosition(index)
	banner.UpdatePosition(position)
}

func (q *Queue) calculatePosition(index int) BannerPosition {
	position := BannerPosition{
		Corner: q.corner,
		Width:  q.bannerWidth,
		Height: q.bannerHeight,
	}

	switch q.corner {
	case CornerTopLeft:
		position.X = 10
		position.Y = 40 + (index * (q.bannerHeight + q.bannerGap))
	case CornerTopRight:
		position.X = 10
		position.Y = 40 + (index * (q.bannerHeight + q.bannerGap))
	case CornerBottomLeft:
		position.X = 10
		position.Y = 10 + (index * (q.bannerHeight + q.bannerGap))
	case CornerBottomRight:
		position.X = 10
		position.Y = 10 + (index * (q.bannerHeight + q.bannerGap))
	default:
		position.X = 10
		position.Y = 40 + (index * (q.bannerHeight + q.bannerGap))
	}

	return position
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
