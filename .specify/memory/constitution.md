# Locus Go Constitution

## Version: 1.0
**Ratified**: 2025-12-25
**Status**: Active

---

## Article I: Go Best Practices

### I.1 Code Style
- Use `gofmt` and `goimports` consistently
- Package names are lowercase, single words (e.g., `launcher`, not `Launcher`)
- Exported names use PascalCase, unexported use camelCase
- Keep files focused (<500 lines when possible)

### I.2 Error Handling
- Explicit error returns, never panic in production code
- Wrap errors with context using `fmt.Errorf("context: %w", err)`
- Handle errors at the appropriate layer (don't let them bubble unnecessarily)

### I.3 Concurrency
- Prefer channels over mutexes for coordination
- Use `sync.RWMutex` for read-heavy data structures
- Goroutines must have clear lifecycle management
- Use `context.Context` for cancellation and deadlines

### I.4 Interface Design
- Interfaces are defined by the consumer, not the producer
- Keep interfaces small (1-2 methods preferred)
- Don't create interfaces "just in case" (YAGNI)

---

## Article II: Architecture Principles

### II.1 Clean Architecture
- `internal/` packages are private - no external imports
- `cmd/` contains only main.go - no business logic
- Domain logic in `internal/` with clear package boundaries

### II.2 Plugin System
- Both launchers and statusbar modules use registry pattern
- Auto-registration via `init()` functions
- Each plugin implements a defined interface

### II.3 IPC-First Design
- All major features must expose IPC commands
- IPC is the primary interface (CLI is secondary)
- Unix socket at `/tmp/locus_socket` for main app
- Separate socket for statusbar: `/tmp/locus_statusbar_socket`

### II.4 GTK Integration
- Use `gotk3` for GTK3 bindings
- GTK operations must happen on main thread
- Use `glib.IdleAdd()` for thread-safe updates
- Layer shell for Wayland overlay positioning

---

## Article III: Testing Standards

### III.1 Test Coverage
- Core logic requires >80% test coverage
- Registry code requires 100% coverage
- Integration tests for complex workflows

### III.2 Test Organization
- Table-driven tests for multiple scenarios
- Use `t.Run()` for subtests
- Mock external dependencies (GTK, system commands)

### III.3 Test Types
- Unit tests for individual functions
- Registry tests for plugin systems
- Integration tests for IPC communication

---

## Article IV: Performance Requirements

### IV.1 Responsiveness
- Launcher search results < 100ms
- Statusbar updates < 16ms (60 FPS)
- IPC command response < 50ms

### IV.2 Resource Usage
- Memory overhead < 50MB idle
- CPU usage < 1% idle
- No memory leaks (verify with `go test -memprofile`)

### IV.3 Blocking Operations
- No blocking operations in main goroutine
- Use goroutines for I/O and expensive computations
- Provide cancellation via context

---

## Article V: Configuration Management

### V.1 Configuration Format
- TOML for configuration files
- Located at `~/.config/locus/config.toml`
- Sensible defaults for all settings

### V.2 Module Configuration
- Each module has its own config section
- Supports hot-reloading where applicable
- Validation on config load

---

## Article VI: Documentation Requirements

### VI.1 Code Comments
- Exported functions must have Go doc comments
- Complex algorithms need inline comments
- Comments explain "why", not "what"

### VI.2 Feature Documentation
- Each feature must have corresponding spec in `.specify/specs/`
- Update `GO_REWRITE_PROGRESS.md` when completing features
- Update architecture docs for major changes

---

## Governance

### Amendment Process
1. Proposed changes must be documented
2. Team review required
3. Version number must increment
4. Change log maintained

### Compliance
- All PRs must verify constitution compliance
- Linting tools check: `gofmt`, `golint`, `go vet`
- CI pipeline enforces test coverage and build success