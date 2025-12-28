package launcher

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type AppUsageRecord struct {
	LaunchCount    int       `json:"launch_count"`
	LastLaunched   time.Time `json:"last_launched"`
	FirstLaunched  time.Time `json:"first_launched"`
	RecentLaunches []int64   `json:"recent_launches"`
}

type FrecencyTracker struct {
	records          map[string]*AppUsageRecord
	mu               sync.RWMutex
	file             string
	maxRecentEntries int
	halfLife         time.Duration
}

func NewFrecencyTracker(dataDir string) (*FrecencyTracker, error) {
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create data directory: %w", err)
	}

	file := filepath.Join(dataDir, "frecency.json")
	tracker := &FrecencyTracker{
		records:          make(map[string]*AppUsageRecord),
		file:             file,
		maxRecentEntries: 10,
		halfLife:         7 * 24 * time.Hour,
	}

	if err := tracker.load(); err != nil {
		log.Printf("[FREQUENCY] Failed to load frecency data: %v", err)
	}

	return tracker, nil
}

func (f *FrecencyTracker) RecordLaunch(appName string) {
	if appName == "" {
		return
	}

	f.mu.Lock()
	defer f.mu.Unlock()

	now := time.Now()

	record, exists := f.records[appName]
	if !exists {
		record = &AppUsageRecord{
			LaunchCount:    0,
			FirstLaunched:  now,
			RecentLaunches: []int64{},
		}
		f.records[appName] = record
	}

	record.LaunchCount++
	record.LastLaunched = now

	record.RecentLaunches = append(record.RecentLaunches, now.Unix())
	if len(record.RecentLaunches) > f.maxRecentEntries {
		record.RecentLaunches = record.RecentLaunches[1:]
	}

	if err := f.save(); err != nil {
		log.Printf("[FREQUENCY] Failed to save frecency data: %v", err)
	}

	log.Printf("[FREQUENCY] Recorded launch for app '%s': count=%d, last_launched=%v", appName, record.LaunchCount, now)
}

func (f *FrecencyTracker) GetFrequencyScore(appName string) float64 {
	f.mu.RLock()
	defer f.mu.RUnlock()

	record, exists := f.records[appName]
	if !exists {
		return 0
	}

	return float64(record.LaunchCount)
}

func (f *FrecencyTracker) GetFrecencyScore(appName string) float64 {
	f.mu.RLock()
	defer f.mu.RUnlock()

	record, exists := f.records[appName]
	if !exists {
		return 0
	}

	now := time.Now()

	frequencyScore := float64(record.LaunchCount)

	recencyScore := f.calculateRecencyScore(record.LastLaunched, now)

	trendScore := f.calculateTrendScore(record.RecentLaunches, now)

	frecency := (frequencyScore * 0.4) + (recencyScore * 0.4) + (trendScore * 0.2)

	return frecency
}

func (f *FrecencyTracker) calculateRecencyScore(lastLaunched, now time.Time) float64 {
	timeSinceLaunch := now.Sub(lastLaunched)

	halfLivesPassed := float64(timeSinceLaunch) / float64(f.halfLife)

	decayFactor := 0.5
	score := decayFactor

	for i := 0; i < int(halfLivesPassed); i++ {
		score *= decayFactor
	}

	if halfLivesPassed > 0 {
		remaining := halfLivesPassed - float64(int(halfLivesPassed))
		score *= (decayFactor * remaining)
	}

	return score * 100
}

func (f *FrecencyTracker) calculateTrendScore(recentLaunches []int64, now time.Time) float64 {
	if len(recentLaunches) < 2 {
		return 0
	}

	totalInterval := recentLaunches[len(recentLaunches)-1] - recentLaunches[0]
	if totalInterval <= 0 {
		return 0
	}

	averageInterval := float64(totalInterval) / float64(len(recentLaunches)-1)

	if averageInterval <= 0 {
		return 0
	}

	launchesPerDay := 24.0 * 3600.0 / averageInterval

	if launchesPerDay > 10 {
		launchesPerDay = 10
	}

	score := (launchesPerDay / 10.0) * 100

	return score
}

func (f *FrecencyTracker) GetUsageStats(appName string) *AppUsageRecord {
	f.mu.RLock()
	defer f.mu.RUnlock()

	record, exists := f.records[appName]
	if !exists {
		return nil
	}

	recordCopy := &AppUsageRecord{
		LaunchCount:    record.LaunchCount,
		LastLaunched:   record.LastLaunched,
		FirstLaunched:  record.FirstLaunched,
		RecentLaunches: make([]int64, len(record.RecentLaunches)),
	}
	copy(record.RecentLaunches, recordCopy.RecentLaunches)

	return recordCopy
}

func (f *FrecencyTracker) GetAllRecords() map[string]*AppUsageRecord {
	f.mu.RLock()
	defer f.mu.RUnlock()

	records := make(map[string]*AppUsageRecord, len(f.records))
	for name, record := range f.records {
		recordCopy := &AppUsageRecord{
			LaunchCount:    record.LaunchCount,
			LastLaunched:   record.LastLaunched,
			FirstLaunched:  record.FirstLaunched,
			RecentLaunches: make([]int64, len(record.RecentLaunches)),
		}
		copy(record.RecentLaunches, recordCopy.RecentLaunches)
		records[name] = recordCopy
	}

	return records
}

func (f *FrecencyTracker) load() error {
	data, err := os.ReadFile(f.file)
	if err != nil {
		if os.IsNotExist(err) {
			log.Printf("[FREQUENCY] No existing frecency data file, starting fresh")
			return nil
		}
		return err
	}

	var records map[string]*AppUsageRecord
	if err := json.Unmarshal(data, &records); err != nil {
		return fmt.Errorf("failed to unmarshal frecency data: %w", err)
	}

	f.mu.Lock()
	f.records = records
	f.mu.Unlock()

	log.Printf("[FREQUENCY] Loaded %d app usage records", len(records))
	return nil
}

func (f *FrecencyTracker) save() error {
	data, err := json.MarshalIndent(f.records, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal frecency data: %w", err)
	}

	if err := os.WriteFile(f.file, data, 0644); err != nil {
		return fmt.Errorf("failed to write frecency data: %w", err)
	}

	return nil
}

func (f *FrecencyTracker) Clear() {
	f.mu.Lock()
	defer f.mu.Unlock()

	f.records = make(map[string]*AppUsageRecord)
	_ = f.save()

	log.Printf("[FREQUENCY] Cleared all usage records")
}

func (f *FrecencyTracker) RemoveApp(appName string) {
	f.mu.Lock()
	defer f.mu.Unlock()

	delete(f.records, appName)
	_ = f.save()

	log.Printf("[FREQUENCY] Removed usage record for app '%s'", appName)
}

type FrecencyMatch struct {
	AppName string
	Score   float64
}

func (f *FrecencyTracker) GetTopApps(limit int) []FrecencyMatch {
	f.mu.RLock()
	defer f.mu.RUnlock()

	scores := make([]FrecencyMatch, 0, len(f.records))

	for appName, record := range f.records {
		now := time.Now()
		frequencyScore := float64(record.LaunchCount)
		recencyScore := f.calculateRecencyScore(record.LastLaunched, now)
		trendScore := f.calculateTrendScore(record.RecentLaunches, now)

		frecency := (frequencyScore * 0.4) + (recencyScore * 0.4) + (trendScore * 0.2)

		scores = append(scores, FrecencyMatch{
			AppName: appName,
			Score:   frecency,
		})
	}

	for i := 0; i < len(scores); i++ {
		for j := i + 1; j < len(scores); j++ {
			if scores[j].Score > scores[i].Score {
				scores[i], scores[j] = scores[j], scores[i]
			}
		}
	}

	if limit > 0 && len(scores) > limit {
		scores = scores[:limit]
	}

	return scores
}
