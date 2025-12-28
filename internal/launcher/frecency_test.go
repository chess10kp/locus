package launcher

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestNewFrecencyTracker(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	if tracker == nil {
		t.Fatal("Expected non-nil tracker")
	}

	if tracker.file != filepath.Join(tempDir, "frecency.json") {
		t.Errorf("Expected file path %s, got %s", filepath.Join(tempDir, "frecency.json"), tracker.file)
	}
}

func TestFrecencyTracker_RecordLaunch(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Chrome")

	stats := tracker.GetUsageStats("Firefox")
	if stats == nil {
		t.Fatal("Expected non-nil stats for Firefox")
	}

	if stats.LaunchCount != 2 {
		t.Errorf("Expected launch count 2, got %d", stats.LaunchCount)
	}

	chromeStats := tracker.GetUsageStats("Chrome")
	if chromeStats.LaunchCount != 1 {
		t.Errorf("Expected launch count 1 for Chrome, got %d", chromeStats.LaunchCount)
	}
}

func TestFrecencyTracker_GetFrequencyScore(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	score := tracker.GetFrequencyScore("NonExistent")
	if score != 0 {
		t.Errorf("Expected frequency score 0 for non-existent app, got %f", score)
	}

	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Firefox")

	score = tracker.GetFrequencyScore("Firefox")
	if score != 3 {
		t.Errorf("Expected frequency score 3, got %f", score)
	}
}

func TestFrecencyTracker_GetFrecencyScore(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	tracker.RecordLaunch("Firefox")
	score := tracker.GetFrecencyScore("Firefox")
	if score <= 0 {
		t.Errorf("Expected positive frecency score for launched app, got %f", score)
	}

	score = tracker.GetFrecencyScore("NonExistent")
	if score != 0 {
		t.Errorf("Expected frecency score 0 for non-existent app, got %f", score)
	}
}

func TestFrecencyTracker_RecencyDecay(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	tracker.RecordLaunch("Firefox")
	recentScore := tracker.GetFrecencyScore("Firefox")

	oldTracker, _ := NewFrecencyTracker(tempDir)
	oldTracker.records = tracker.records
	for key, record := range oldTracker.records {
		record.LastLaunched = time.Now().Add(-30 * 24 * time.Hour)
		oldTracker.records[key] = record
	}
	oldScore := oldTracker.GetFrecencyScore("Firefox")

	if oldScore >= recentScore {
		t.Errorf("Expected old score %f to be less than recent score %f", oldScore, recentScore)
	}
}

func TestFrecencyTracker_GetTopApps(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Chrome")
	tracker.RecordLaunch("Chrome")
	tracker.RecordLaunch("Terminal")

	topApps := tracker.GetTopApps(10)
	if len(topApps) != 3 {
		t.Errorf("Expected 3 top apps, got %d", len(topApps))
	}

	if topApps[0].AppName != "Firefox" {
		t.Errorf("Expected Firefox to be top app, got %s", topApps[0].AppName)
	}

	if topApps[0].Score < topApps[1].Score {
		t.Errorf("Expected first app score %f to be >= second app score %f", topApps[0].Score, topApps[1].Score)
	}
}

func TestFrecencyTracker_Persistence(t *testing.T) {
	tempDir := t.TempDir()
	tracker1, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create first tracker: %v", err)
	}

	tracker1.RecordLaunch("Firefox")
	tracker1.RecordLaunch("Firefox")
	tracker1.RecordLaunch("Chrome")

	tracker2, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create second tracker: %v", err)
	}

	ffStats := tracker2.GetUsageStats("Firefox")
	if ffStats == nil {
		t.Fatal("Expected Firefox stats to be persisted")
	}

	if ffStats.LaunchCount != 2 {
		t.Errorf("Expected persisted launch count 2, got %d", ffStats.LaunchCount)
	}
}

func TestFrecencyTracker_RemoveApp(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Chrome")

	tracker.RemoveApp("Firefox")

	ffStats := tracker.GetUsageStats("Firefox")
	if ffStats != nil {
		t.Error("Expected Firefox stats to be removed")
	}

	chromeStats := tracker.GetUsageStats("Chrome")
	if chromeStats == nil {
		t.Error("Expected Chrome stats to still exist")
	}
}

func TestFrecencyTracker_Clear(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Chrome")

	tracker.Clear()

	records := tracker.GetAllRecords()
	if len(records) != 0 {
		t.Errorf("Expected 0 records after clear, got %d", len(records))
	}

	ffStats := tracker.GetUsageStats("Firefox")
	if ffStats != nil {
		t.Error("Expected Firefox stats to be cleared")
	}
}

func TestFrecencyTracker_GetAllRecords(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	tracker.RecordLaunch("Firefox")
	tracker.RecordLaunch("Chrome")

	records := tracker.GetAllRecords()
	if len(records) != 2 {
		t.Errorf("Expected 2 records, got %d", len(records))
	}

	if _, exists := records["Firefox"]; !exists {
		t.Error("Expected Firefox record to exist")
	}

	if _, exists := records["Chrome"]; !exists {
		t.Error("Expected Chrome record to exist")
	}
}

func TestFrecencyTracker_CalculateTrendScore(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	now := time.Now()

	tracker.RecordLaunch("Firefox")
	time.Sleep(10 * time.Millisecond)
	tracker.RecordLaunch("Firefox")

	score := tracker.GetFrecencyScore("Firefox")
	if score <= 0 {
		t.Errorf("Expected positive trend score for frequently launched app, got %f", score)
	}
}

func TestFrecencyTracker_MultipleRecentLaunches(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	for i := 0; i < 15; i++ {
		tracker.RecordLaunch("Firefox")
	}

	stats := tracker.GetUsageStats("Firefox")
	if len(stats.RecentLaunches) > 10 {
		t.Errorf("Expected max 10 recent launches, got %d", len(stats.RecentLaunches))
	}

	if stats.LaunchCount != 15 {
		t.Errorf("Expected total launch count 15, got %d", stats.LaunchCount)
	}
}

func TestFrecencyTracker_FilePersistence(t *testing.T) {
	tempDir := t.TempDir()
	tracker, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create frecency tracker: %v", err)
	}

	tracker.RecordLaunch("Firefox")

	filePath := filepath.Join(tempDir, "frecency.json")
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		t.Error("Expected frecency.json file to exist after recording launch")
	}

	tracker2, err := NewFrecencyTracker(tempDir)
	if err != nil {
		t.Fatalf("Failed to create second tracker: %v", err)
	}

	ffStats := tracker2.GetUsageStats("Firefox")
	if ffStats == nil || ffStats.LaunchCount != 1 {
		t.Error("Expected data to be loaded from file correctly")
	}
}
