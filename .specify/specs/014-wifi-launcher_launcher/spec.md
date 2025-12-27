# Launcher Specification: wifi-launcher

**Type**: Launcher Implementation
**Feature ID**: 018
**Python Reference**: `python_backup/launchers/wifi_launcher.py`

---

## Launcher Definition

### Triggers
- Primary: `wifi`
- Aliases: `w`

### Purpose
WiFi network management launcher that displays available networks, manages connections, and provides power/scan controls using NetworkManager (nmcli).

---

## User Stories

### US-001: Connect to WiFi Networks (P1)
**Actor**: End User
**Goal**: Easily connect to available WiFi networks
**Benefit**: Simplified WiFi management without terminal commands

**Independent Test**: Enable WiFi, trigger launcher, verify networks appear and connection works

**Acceptance Scenarios**:
1. **Given** WiFi enabled, **When** user types `>wifi`, **Then** available networks and status appear
2. **Given** saved network shown, **When** user selects it, **Then** connection toggles (connect/disconnect)
3. **Given** available network shown, **When** user selects it, **Then** connection attempt made
4. **Given** connected to network, **When** user selects "Disconnect", **Then** connection terminates

---

## Requirements

### Functional Requirements
- **FR-018-001**: System MUST check for nmcli availability on startup
- **FR-018-002**: System MUST display WiFi power status (on/off)
- **FR-018-003**: System MUST show list of saved/configured networks
- **FR-018-004**: System MUST scan and display available networks
- **FR-018-005**: System MUST indicate current connection status
- **FR-018-006**: System MUST allow toggling WiFi power state
- **FR-018-007**: System MUST allow connecting to saved networks
- **FR-018-008**: System MUST allow disconnecting from current network
- **FR-018-009**: System MUST provide rescanning capability
- **FR-018-010**: System MUST support forgetting saved networks
- **FR-018-011**: System MUST cache scan results for 10 seconds

### Non-Functional Requirements
- **Performance**: Network scanning < 5 seconds, status queries < 100ms
- **Dependencies**: Requires nmcli (NetworkManager)
- **Caching**: Scan results cached for 10 seconds
- **Error handling**: Graceful fallback if NetworkManager unavailable

---

## Dependencies

### External Dependencies
- `nmcli` - NetworkManager command-line interface

### Internal Dependencies
- WiFi utility functions for NetworkManager integration

---

## Success Criteria

- **SC-018-001**: All saved networks display with correct connection status
- **SC-018-002**: Available networks appear after scanning
- **SC-018-003**: Connection/disconnection works for all network types
- **SC-018-004**: Power toggle and rescan functions work correctly
- **SC-018-005**: Tab completion works for network names and commands

---

## Out of Scope
- WiFi network configuration (advanced settings)
- VPN management
- Ethernet connection management
- Network diagnostics

---

## Risks & Assumptions

### Risks
- NetworkManager/nmcli API changes between versions
- Complex WiFi security configurations
- Race conditions during connection attempts
- Network scanning timeouts

### Assumptions
- NetworkManager is the system network manager
- User has appropriate permissions for network operations
- nmcli commands are stable across versions

---

## Python Reference Analysis

**File**: `python_backup/launchers/wifi_launcher.py`

**Key Components to Port**:
1. `WifiHook` class - Handles network selection and control actions
2. `populate()` method - Shows status controls and network lists
3. `check_dependencies()` - Verifies nmcli availability
4. Scan caching mechanism (10-second cache)
5. Network status display with connection indicators

**Go Adaptation Notes**:
- Python: subprocess.run with nmcli → Go: exec.Command with output parsing
- Python: Global utility functions → Go: wifi package with interfaces
- Python: Dict network data → Go: struct types for networks
- Python: Time-based caching → Go: time tracking with mutex protection
- Need to handle nmcli output parsing and error states