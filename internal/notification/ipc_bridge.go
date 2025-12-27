package notification

import (
	"encoding/json"
	"fmt"
	"log"
	"net"
	"strings"
	"sync"

	"github.com/chess10kp/locus/internal/config"
)

type IPCRequest struct {
	Command string                 `json:"command"`
	Params  map[string]interface{} `json:"params"`
}

type IPCResponse struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data"`
	Error   string      `json:"error,omitempty"`
}

type IPCBridge struct {
	store      *Store
	socketPath string
	listener   net.Listener
	running    bool
	mu         sync.Mutex
}

func NewIPCBridge(store *Store, socketPath string) *IPCBridge {
	return &IPCBridge{
		store:      store,
		socketPath: socketPath,
		running:    false,
	}
}

func (b *IPCBridge) Start() error {
	b.mu.Lock()
	defer b.mu.Unlock()

	if b.running {
		return fmt.Errorf("IPC bridge already running")
	}

	conn, err := net.Listen("unix", b.socketPath)
	if err != nil {
		return fmt.Errorf("failed to listen on socket %s: %w", b.socketPath, err)
	}

	b.listener = conn
	b.running = true

	log.Printf("Notification IPC bridge listening on %s", b.socketPath)

	go b.acceptConnections()

	return nil
}

func (b *IPCBridge) Stop() error {
	b.mu.Lock()
	defer b.mu.Unlock()

	if !b.running {
		return nil
	}

	b.running = false

	if b.listener != nil {
		b.listener.Close()
		b.listener = nil
	}

	log.Println("Notification IPC bridge stopped")

	return nil
}

func (b *IPCBridge) acceptConnections() {
	for b.running {
		conn, err := b.listener.Accept()
		if err != nil {
			if b.running {
				log.Printf("Error accepting connection: %v", err)
			}
			continue
		}

		go b.handleConnection(conn)
	}
}

func (b *IPCBridge) handleConnection(conn net.Conn) {
	defer conn.Close()

	buf := make([]byte, 4096)
	n, err := conn.Read(buf)
	if err != nil {
		log.Printf("Error reading from connection: %v", err)
		return
	}

	request := IPCRequest{}
	if err := json.Unmarshal(buf[:n], &request); err != nil {
		response := IPCResponse{
			Success: false,
			Error:   fmt.Sprintf("failed to unmarshal request: %v", err),
		}
		b.sendResponse(conn, response)
		return
	}

	response := b.handleRequest(request)
	b.sendResponse(conn, response)
}

func (b *IPCBridge) handleRequest(request IPCRequest) IPCResponse {
	switch request.Command {
	case "get_unread_count":
		return b.handleGetUnreadCount()
	case "get_notifications":
		return b.handleGetNotifications(request.Params)
	case "search":
		return b.handleSearch(request.Params)
	case "mark_read":
		return b.handleMarkRead(request.Params)
	case "mark_all_read":
		return b.handleMarkAllRead()
	case "remove":
		return b.handleRemove(request.Params)
	case "clear_all":
		return b.handleClearAll()
	default:
		return IPCResponse{
			Success: false,
			Error:   fmt.Sprintf("unknown command: %s", request.Command),
		}
	}
}

func (b *IPCBridge) handleGetUnreadCount() IPCResponse {
	return IPCResponse{
		Success: true,
		Data:    b.store.GetUnreadCount(),
	}
}

func (b *IPCBridge) handleGetNotifications(params map[string]interface{}) IPCResponse {
	limit := 50
	if limitParam, ok := params["limit"].(float64); ok {
		limit = int(limitParam)
	}

	appName := ""
	if appNameParam, ok := params["app_name"].(string); ok {
		appName = appNameParam
	}

	var notifs []*Notification
	if appName != "" {
		notifs = b.store.GetNotificationsByApp(appName)
	} else {
		notifs = b.store.GetNotifications(limit)
	}

	return IPCResponse{
		Success: true,
		Data:    notifs,
	}
}

func (b *IPCBridge) handleSearch(params map[string]interface{}) IPCResponse {
	query := ""
	if queryParam, ok := params["query"].(string); ok {
		query = queryParam
	}

	return IPCResponse{
		Success: true,
		Data:    b.store.Search(query),
	}
}

func (b *IPCBridge) handleMarkRead(params map[string]interface{}) IPCResponse {
	id, ok := params["id"].(string)
	if !ok {
		return IPCResponse{
			Success: false,
			Error:   "missing id parameter",
		}
	}

	success := b.store.MarkAsRead(id)
	return IPCResponse{
		Success: success,
		Data:    success,
	}
}

func (b *IPCBridge) handleMarkAllRead() IPCResponse {
	count := b.store.MarkAllAsRead()
	return IPCResponse{
		Success: true,
		Data:    count,
	}
}

func (b *IPCBridge) handleRemove(params map[string]interface{}) IPCResponse {
	id, ok := params["id"].(string)
	if !ok {
		return IPCResponse{
			Success: false,
			Error:   "missing id parameter",
		}
	}

	success := b.store.RemoveNotification(id)
	return IPCResponse{
		Success: success,
		Data:    success,
	}
}

func (b *IPCBridge) handleClearAll() IPCResponse {
	count := b.store.ClearAll()
	return IPCResponse{
		Success: true,
		Data:    count,
	}
}

func (b *IPCBridge) sendResponse(conn net.Conn, response IPCResponse) {
	data, err := json.Marshal(response)
	if err != nil {
		log.Printf("Error marshaling response: %v", err)
		return
	}

	if _, err := conn.Write(data); err != nil {
		log.Printf("Error writing response: %v", err)
	}
}

func QueryNotificationStore(socketPath, command string, params map[string]interface{}) (*IPCResponse, error) {
	conn, err := net.Dial("unix", socketPath)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to notification daemon: %w", err)
	}
	defer conn.Close()

	request := IPCRequest{
		Command: command,
		Params:  params,
	}

	requestData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	if _, err := conn.Write(requestData); err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}

	buf := make([]byte, 4096)
	n, err := conn.Read(buf)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var response IPCResponse
	if err := json.Unmarshal(buf[:n], &response); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	return &response, nil
}

func QueryNotificationStoreSimple(socketPath, command string) (*IPCResponse, error) {
	return QueryNotificationStore(socketPath, command, nil)
}

func GetUnreadCount(socketPath string) (int, error) {
	response, err := QueryNotificationStoreSimple(socketPath, "get_unread_count")
	if err != nil {
		return 0, err
	}

	if !response.Success {
		return 0, fmt.Errorf("failed to get unread count: %s", response.Error)
	}

	if count, ok := response.Data.(float64); ok {
		return int(count), nil
	}

	return 0, fmt.Errorf("invalid response data type")
}

type Manager struct {
	store     *Store
	queue     *Queue
	daemon    *Daemon
	ipcBridge *IPCBridge
	config    *config.NotificationConfig
	running   bool
	mu        sync.Mutex
}

func NewManager(cfg *config.NotificationConfig) (*Manager, error) {
	socketPath := cfg.History.PersistPath + ".sock"

	store, err := NewStore(
		cfg.History.MaxHistory,
		cfg.History.MaxAgeDays,
		cfg.History.PersistPath,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create notification store: %w", err)
	}

	corner := Corner(cfg.Daemon.Position)
	queue := NewQueue(store, cfg.Daemon.MaxBanners, cfg.Daemon.BannerGap, cfg.Daemon.BannerHeight, corner)

	m := &Manager{
		store:   store,
		queue:   queue,
		config:  cfg,
		running: false,
	}

	m.daemon = NewDaemon(store, queue, cfg)
	m.ipcBridge = NewIPCBridge(store, socketPath)

	return m, nil
}

func (m *Manager) Start() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.running {
		return fmt.Errorf("manager already running")
	}

	m.queue.SetCallbacks(m.onBannerClose, m.onBannerAction)

	if err := m.ipcBridge.Start(); err != nil {
		return fmt.Errorf("failed to start IPC bridge: %w", err)
	}

	if err := m.daemon.Start(); err != nil {
		m.ipcBridge.Stop()
		return fmt.Errorf("failed to start daemon: %w", err)
	}

	go m.listenStoreEvents()

	m.running = true

	log.Println("Notification manager started")

	return nil
}

func (m *Manager) Stop() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if !m.running {
		return nil
	}

	m.running = false

	m.daemon.Stop()
	m.ipcBridge.Stop()
	m.queue.Cleanup()

	log.Println("Notification manager stopped")

	return nil
}

func (m *Manager) onBannerClose(notifID string) {
	m.daemon.emitNotificationClosed(m.getDaemonID(notifID), CloseReasonDismissed)
}

func (m *Manager) onBannerAction(notifID, actionKey string) {
	daemonID := m.getDaemonID(notifID)
	if daemonID > 0 {
		m.daemon.emitActionInvoked(daemonID, actionKey)
	}
}

func (m *Manager) getDaemonID(notifID string) uint32 {
	m.daemon.mu.Lock()
	defer m.daemon.mu.Unlock()

	for daemonID, id := range m.daemon.activeNotifs {
		if id == notifID {
			return daemonID
		}
	}
	return 0
}

func (m *Manager) listenStoreEvents() {
	for event := range m.store.Events() {
		switch event.Type {
		case "unread_count_changed":
			log.Printf("Unread count changed: %d", event.UnreadCount)
		}
	}
}

func (m *Manager) GetStore() *Store {
	return m.store
}

func (m *Manager) GetQueue() *Queue {
	return m.queue
}

func (m *Manager) GetSocketPath() string {
	return m.ipcBridge.socketPath
}

func normalizeSocketPath(path string) string {
	return strings.ReplaceAll(path, "notifications.json", "notifications.sock")
}
