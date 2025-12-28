## High Priority (High Impact, Medium Effort)

### 5. Statusbar Module IPC Message Loss

**Category**: Performance  
**Files**: `internal/statusbar/events.go:268-274`, `internal/statusbar/scheduler.go:325-363`

**Current Problem**:
Messages are dropped silently when channel is full:

```go
select {
case l.ipcChannel <- message:
default:
    log.Printf("IPC channel full, dropping message: %s", message)
}
```

**Proposed Improvement**:
```go
// Use buffered channel with monitoring
type IPCMonitor struct {
    channel      chan string
    droppedCount  atomic.Int64
    lastDropped  time.Time
}

func (m *IPCMonitor) SendMessage(message string) {
    select {
    case m.channel <- message:
    default:
        count := m.droppedCount.Add(1)
        if count%100 == 0 {
            log.Printf("WARNING: %d IPC messages dropped (last: %s ago)", 
                count, time.Since(m.lastDropped))
            m.lastDropped = time.Now()
        }
        // Consider: Fallback to queue or file
    }
}
```

**Impact**: No silent data loss, monitoring for capacity issues

---

### 6. Memory Leak in Timer Cancellation

**Category**: Resource Management  
**Files**: `internal/core/launcher.go:10000-1014`

**Current Problem**:
```go
func (l *Launcher) stopAndDrainSearchTimer() {
    if l.searchTimer != nil {
        if !l.searchTimer.Stop() {
            // Timer already fired, drain the channel
            if l.searchTimer.C != nil {  // Redundant - Timer.C is always non-nil
                select {
                case <-l.searchTimer.C:
                default:
                }
            }
        }
        l.searchTimer = nil
    }
}
```

Race condition: timer could fire between `Stop()` check and the select.

**Proposed Improvement**:
```go
func (l *Launcher) stopAndDrainSearchTimer() {
    if l.searchTimer == nil {
        return
    }
    
    if !l.searchTimer.Stop() {
        // Timer fired, drain it
        <-l.searchTimer.C
    }
    l.searchTimer = nil
}
```

**Impact**: Prevents goroutine leaks, more reliable timer management

---

## Medium Priority (Medium Impact, Medium Effort)

### 7. Duplication in Launcher Implementations

**Category**: Code Patterns  
**Files**: `internal/launcher/builtin.go:10-194`

**Current Problem**:
Multiple launchers have nearly identical structure:

```go
type ShellLauncher struct { config *config.Config }
type WebLauncher struct { config *config.Config }
type CalcLauncher struct { config *config.Config }
// All have similar Populate, Name, CommandTriggers, GetHooks, Rebuild, Cleanup
```

**Proposed Improvement**:
```go
// Create base launcher with common patterns
type SimpleLauncher struct {
    config       *config.Config
    name         string
    triggers     []string
    icon         string
    populateFunc func(query string) []*LauncherItem
}

func (l *SimpleLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
    return l.populateFunc(query)
}

func (l *SimpleLauncher) Name() string {
    return l.name
}

func (l *SimpleLauncher) CommandTriggers() []string {
    return l.triggers
}

func (l *SimpleLauncher) GetSizeMode() LauncherSizeMode {
    return LauncherSizeModeDefault
}

func (l *SimpleLauncher) GetHooks() []Hook {
    return []Hook{}
}

func (l *SimpleLauncher) Rebuild(ctx *LauncherContext) error {
    return nil
}

func (l *SimpleLauncher) Cleanup() {}

func (l *SimpleLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
    return nil, false
}

func NewSimpleLauncher(name, icon string, triggers []string, populateFunc func(string) []*LauncherItem) Launcher {
    return &SimpleLauncher{
        name:         name,
        icon:         icon,
        triggers:     triggers,
        populateFunc: populateFunc,
    }
}
```

**Impact**: 50% code reduction for simple launchers, easier to add new ones

---

func (l *FileLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
    q := strings.TrimSpace(query)
    
    // Check cache first
    l.cacheLock.RLock()
    if cached, ok := l.cache.Get(q); ok {
        l.cacheLock.RUnlock()
        return cached
    }
    l.cacheLock.RUnlock()
    
    // Async search
    resultChan := make(chan []*LauncherItem, 1)
    go func() {
        results := l.doSearch(q)
        resultChan <- results
    }()
    
    // Return cached or loading state immediately
    return l.getLoadingState()
}

func (l *FileLauncher) doSearch(query string) []*LauncherItem {
    // Perform blocking search
    // Cache results
    // Trigger UI update via IPC
}
```

**Impact**: Launcher remains responsive during file searches

---

### 9. Inconsistent Module Error Handling

**Category**: Error Handling  
**Files**: `internal/statusbar/registry.go:349-356`

**Current Problem**:
```go
func (r *ModuleRegistry) UpdateModuleWidget(name string, widget gtk.IWidget) error {
    errChan := make(chan error, 1)
    glib.IdleAdd(func() {
        err := module.UpdateWidget(widget)
        errChan <- err
    })
    return <-errChan  // Blocks forever if IdleAdd never calls function
}
```

**Proposed Improvement**:
```go
func (r *ModuleRegistry) UpdateModuleWidget(name string, widget gtk.IWidget) error {
    errChan := make(chan error, 1)
    glib.IdleAdd(func() {
        err := module.UpdateWidget(widget)
        select {
        case errChan <- err:
        default:
            log.Printf("Module %s update result dropped", name)
        }
    })
    
    select {
    case err := <-errChan:
        return err
    case <-time.After(5 * time.Second):
        return fmt.Errorf("timeout updating module %s", name)
    }
}
```

**Impact**: Prevents deadlocks, adds timeout handling

---

### 10. No Module Health Monitoring

**Category**: Extensibility  
**Files**: `internal/statusbar/scheduler.go:89-126`

**Current Problem**:
No tracking of module failures. If a module repeatedly fails, it silently degrades performance.

**Proposed Improvement**:
```go
type ModuleHealth struct {
    Failures      int
    LastFailure   time.Time
    ErrorCount    int
    SuccessCount  int
    IsDisabled   bool
}

func (s *UpdateScheduler) ScheduleModule(name string, widget gtk.IWidget) error {
    // Check if module is temporarily disabled
    if health, ok := s.health[name]; ok && health.IsDisabled {
        if time.Since(health.LastFailure) > time.Minute*5 {
            // Re-enable after cooldown
            health.IsDisabled = false
        } else {
            return fmt.Errorf("module %s is disabled due to failures", name)
        }
    }
    // ... continue scheduling
}

func (s *UpdateScheduler) recordModuleError(name string, err error) {
    health := s.health[name]
    health.ErrorCount++
    health.LastFailure = time.Now()
    
    if health.ErrorCount > 5 && health.SuccessCount == 0 {
        // Disable module
        health.IsDisabled = true
        log.Printf("Disabling module %s due to repeated failures", name)
    }
}
```

**Impact**: Prevents cascading failures, better system stability

---

### 11. Hardcoded Keyboard Shortcuts

**Category**: Extensibility  
**Files**: `internal/core/launcher.go:691-772`

**Current Problem**:
Keyboard shortcuts are hardcoded in the code:

```go
case gdk.KEY_1: index = 0
case gdk.KEY_2: index = 1
// ... repeated for all 9 keys
```

**Proposed Improvement**:
```go
// Add to config.Keys.QuickSelect map[string]int
keyMap := map[gdk.KeyValue]int{}
for k, v := range l.config.Launcher.Keys.QuickSelect {
    keyVal, ok := keyNameToGdkKey[k]
    if ok {
        keyMap[keyVal] = v
    }
}

if state&uint(gdk.MOD1_MASK) != 0 {
    if index, ok := keyMap[key]; ok {
        // Use index
    }
}
```

**Impact**: Users can customize keybindings via config, more flexible

---

## Low Priority (Low Impact, High Effort)

### 12. Missing Architecture Documentation

**Category**: Documentation  
**Files**: `docs/` directory

**Current Problem**:
- `STATUSBAR_ARCHITECTURE.md` exists but no equivalent for launcher
- No component interaction diagrams
- No data flow documentation

**Proposed Improvement**:
```
docs/
  architecture/
    overview.md                  - High-level system architecture
    launcher-architecture.md    - Launcher deep dive
    statusbar-architecture.md    - Statusbar deep dive
    data-flow.md                 - How data flows through system
    performance.md               - Performance characteristics
    adding-components.md         - Guide for adding launchers/modules
```

**Impact**: Easier onboarding, better maintenance

---

### 13. No Plugin Infrastructure

**Category**: Extensibility  
**Files**: All launcher/statusbar files

**Current Problem**:
Adding custom launchers or modules requires modifying source code. No way to load from external shared libraries or plugins.

**Proposed Improvement**:
```go
// Use Go plugins (requires careful design)
type Plugin interface {
    Name() string
    Version() string
    Init(config map[string]interface{}) error
    Cleanup() error
}

type LauncherPlugin interface {
    Plugin
    CreateLauncher(cfg *config.Config) Launcher
}

func LoadPlugin(path string) (Plugin, error) {
    plug, err := plugin.Open(path)
    if err != nil {
        return nil, err
    }
    
    symLauncher, err := plug.Lookup("NewMyLauncher")
    if err != nil {
        return nil, err
    }
    
    return symLauncher.(LauncherPlugin), nil
}
```

**Impact**: True extensibility without recompilation

---

### 14. Test Coverage Gaps

**Category**: Testing  
**Files**: Only 3 test files exist

**Current Problem**:
- `action_data_test.go`, `registry_test.go`, `hooks_test.go` exist
- No tests for critical UI code in `launcher.go`
- No integration tests for statusbar scheduler
- No performance benchmarks

**Proposed Improvement**:
```go
// Add launcher_test.go
func TestLauncherWidgetPool(t *testing.T) {
    pool := NewWidgetPool()
    row1 := pool.GetOrCreateRow()
    pool.ReturnRow(row1)
    
    row2 := pool.GetOrCreateRow()
    assert.Equal(t, row1, row2) // Should reuse
}

// Add scheduler_test.go
func TestSchedulerModuleFailure(t *testing.T) {
    // Test module health monitoring
}

// Add benchmarks
func BenchmarkLauncherSearch(b *testing.B) {
    // Benchmark search performance
}
```

**Impact**: Better code quality, catch regressions

---

### 15. No Metrics/Profiling Hooks

**Category**: Performance  
**Files**: Throughout codebase

**Current Problem**:
No built-in metrics collection or profiling hooks. Performance issues require manual instrumentation.

**Proposed Improvement**:
```go
type MetricsCollector struct {
    searchLatency  prometheus.Histogram
    cacheHitRate  prometheus.Gauge
    moduleErrors  prometheus.Counter
}

func (l *Launcher) recordSearch(duration time.Duration) {
    l.metrics.searchLatency.Observe(duration.Seconds())
}

// Expose metrics endpoint
func StartMetricsServer(addr string) {
    http.Handle("/metrics", promhttp.Handler())
    go http.ListenAndServe(addr, nil)
}
```

**Impact**: Production monitoring, easier debugging

---

## Summary by Category

| Category | Count | Total Impact |
|----------|--------|-------------|
| Performance | 4 | High |
| Error Handling | 3 | Medium-High |
| Extensibility | 4 | High |
| Code Patterns | 2 | Medium |
| Resource Management | 1 | High |
| Configuration | 1 | Medium |
| Testing | 1 | Medium |
| Documentation | 1 | Low-Medium |

## Implementation Roadmap

### Phase 1: Quick Wins (Week 1)
2. Add config validation (#2)
3. Improve error reporting (#3)

### Phase 2: High Priority (Weeks 2-3)
4. Refactor launcher registration (#4)
5. Fix IPC message loss (#5)
6. Fix timer memory leak (#6)

### Phase 3: Medium Priority (Weeks 4-6)
7. Reduce launcher duplication (#7)
8. Make file search async (#8)
9. Add module timeouts (#9)
10. Implement health monitoring (#10)
11. Make keyboard shortcuts configurable (#11)

### Phase 4: Long-term (Ongoing)
12. Complete architecture docs (#12)
13. Design plugin system (#13)
14. Increase test coverage (#14)
15. Add metrics infrastructure (#15)

## Prioritization Matrix

```
High Impact, Low Effort (Start Here):
├─ #1 Widget Pool
├─ #2 Config Validation
└─ #3 Error Reporting

High Impact, Medium Effort:
├─ #4 Launcher Registration
├─ #5 IPC Message Loss
└─ #6 Timer Memory Leak

Medium Impact, Medium Effort:
├─ #7 Code Duplication
├─ #8 File Search Async
├─ #9 Module Timeouts
├─ #10 Health Monitoring
└─ #11 Keyboard Shortcuts

Low Impact, High Effort (Long-term):
├─ #12 Documentation
├─ #13 Plugin System
├─ #14 Test Coverage
└─ #15 Metrics
```

## Metrics for Success

Track these metrics to measure improvement:

- **Performance**: Search latency, GC pause time, memory usage
- **Reliability**: Error rate, crash rate, module failure rate
- **Maintainability**: Lines of code per launcher/module, test coverage
- **Extensibility**: Time to add new launcher/module, number of third-party plugins

## Related Documents

- [Launcher Data Flow](LAUNCHER_DATA_FLOW.md) - Detailed data flow documentation
- [Statusbar Architecture](STATUSBAR_ARCHITECTURE.md) - Statusbar module guide
- [Adding New Launcher](adding_new_launcher.md) - Launcher creation guide
