# Launcher Specification: bluetooth-launcher

**Type**: Launcher Implementation
**Feature ID**: 016
**Python Reference**: `python_backup/launchers/bluetooth_launcher.py`

---

## Launcher Definition

### Triggers
- Primary: `bluetooth`
- Aliases: `bt`

### Purpose
Bluetooth device management launcher that allows users to control Bluetooth power, scanning, pairing, and discoverability settings, as well as connect/disconnect paired devices.

---

## User Stories

### US-001: Control Bluetooth Settings (P1)
**Actor**: Power User
**Goal**: Manage Bluetooth adapter settings
**Benefit**: Easy control of Bluetooth power and visibility

**Independent Test**: Toggle Bluetooth power, verify status changes

**Acceptance Scenarios**:
1. **Given** Bluetooth launcher active, **When** user selects "Power: on/off", **Then** Bluetooth power toggles
2. **Given** Bluetooth launcher active, **When** user selects "Scan: on/off", **Then** device scanning toggles
3. **Given** Bluetooth launcher active, **When** user selects "Pairable: on/off", **Then** pairing mode toggles
4. **Given** Bluetooth launcher active, **When** user selects "Discoverable: on/off", **Then** discoverability toggles

---

## Requirements

### Functional Requirements
- **FR-016-001**: System MUST check for bluetoothctl availability on startup
- **FR-016-002**: System MUST display current Bluetooth adapter status (power, scan, pairable, discoverable)
- **FR-016-003**: System MUST show list of paired devices with connection status
- **FR-016-004**: System MUST allow toggling Bluetooth power state
- **FR-016-005**: System MUST allow toggling device scanning
- **FR-016-006**: System MUST allow toggling pairable/discoverable modes
- **FR-016-007**: System MUST allow connecting/disconnecting paired devices
- **FR-016-008**: System MUST provide tab completion for status items and device names

### Non-Functional Requirements
- **Performance**: Status queries < 100ms, device listing < 500ms
- **Dependencies**: Requires bluetoothctl (bluez-utils)
- **Error handling**: Graceful fallback if Bluetooth unavailable
- **Security**: No sensitive data exposure

---

## Dependencies

### External Dependencies
- `bluetoothctl` - Bluetooth control utility from bluez

### Internal Dependencies
- Bluetooth utility functions for adapter and device management

---

## Success Criteria

- **SC-016-001**: All Bluetooth settings toggle correctly
- **SC-016-002**: Device connection status updates in real-time
- **SC-016-003**: Tab completion works for all items
- **SC-016-004**: Graceful handling when Bluetooth hardware unavailable

---

## Out of Scope
- Bluetooth device pairing (new device discovery)
- Audio profile management
- Bluetooth file transfer
- Advanced Bluetooth configuration

---

## Risks & Assumptions

### Risks
- Bluetooth stack differences between Linux distributions
- bluetoothctl command timeouts or hangs
- Race conditions in status updates

### Assumptions
- bluez Bluetooth stack is installed and configured
- User has appropriate permissions for Bluetooth control
- bluetoothctl commands are stable across versions

---

## Python Reference Analysis

**File**: `python_backup/launchers/bluetooth_launcher.py`

**Key Components to Port**:
1. `BluetoothHook` class - Handles status toggles and device connections
2. `populate()` method - Shows status items and device list
3. `check_dependencies()` - Verifies bluetoothctl availability
4. Status checking functions (power_on, scan_on, etc.)
5. Device enumeration and connection status

**Go Adaptation Notes**:
- Python: subprocess.run with bluetoothctl → Go: exec.Command with proper error handling
- Python: Global utility functions → Go: bluetooth package with interfaces
- Python: Dict action_data for devices → Go: struct with MAC address and metadata
- Python: Exception handling → Go: error returns with context
- Need to handle bluetoothctl timeouts and parsing output