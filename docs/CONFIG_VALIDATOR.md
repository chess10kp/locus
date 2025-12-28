# Config Validator

A tool to validate Locus configuration files for valid variables and values.

## Usage

```bash
# Validate default config
./config-validator

# Validate specific config file
./config-validator /path/to/config.toml

# Validate example config
./config-validator config.toml.example
```

## What It Checks

The validator checks the following:

### Window Settings
- Width: 100-4000 pixels
- Height: 100-4000 pixels

### Search Settings
- Max results: 1-1000
- Max command results: 1-1000
- Debounce delay: 0-5000ms

### Status Bar
- Height: 10-100px

### Notification Daemon
- Max banners: 1-20
- Banner gap: 0-50px
- Banner width: 100-2000px
- Banner height: 50-500px
- Animation duration: 0-2000ms
- Position: one of (top-left, top-center, top-right, bottom-left, bottom-center, bottom-right)

### Notification History
- Max history: 0-10000
- Max age days: 1-365

### Notification Timeouts
- Low: 0-60000ms
- Normal: 0-60000ms
- Critical: -1 (no timeout) or 0-60000ms

### Icons
- Icon size: 16-256
- Cache size: 10-10000

### Performance
- Cache max age hours: 1-168
- Search cache size: 10-10000
- Max visible results: 1-100

### Behavior
- Max recent apps: 0-50
- Desktop launcher fast path requires max_recent_apps > 0

### Lock Screen
- Max attempts: 1-10
- Enabled requires password or password_hash

## Example Output

### Valid Config
```
Validating config: ~/.config/locus/config.toml
✅ Config is valid!
```

### Invalid Config
```
Validating config: ~/.config/locus/config.toml
❌ Config validation failed: config validation failed: invalid window width: 5000 (must be 100-4000)
```

## Building

```bash
go build -o config-validator ./cmd/config-validator
```
