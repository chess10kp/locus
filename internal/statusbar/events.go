package statusbar

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"sync"
	"time"

	"github.com/gotk3/gotk3/glib"
)

// EventListener is the base interface for all event listeners
type EventListener interface {
	Start(callback func()) error
	Stop() error
	Cleanup()
	IsRunning() bool
}

// BaseEventListener provides a common base implementation
type BaseEventListener struct {
	running bool
	ctx     context.Context
	cancel  context.CancelFunc
	mu      sync.RWMutex
}

// NewBaseEventListener creates a new base event listener
func NewBaseEventListener() *BaseEventListener {
	ctx, cancel := context.WithCancel(context.Background())
	return &BaseEventListener{
		running: false,
		ctx:     ctx,
		cancel:  cancel,
	}
}

// IsRunning returns whether the listener is running
func (l *BaseEventListener) IsRunning() bool {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.running
}

// setRunning sets the running state
func (l *BaseEventListener) setRunning(running bool) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.running = running
}

// Stop stops the listener
func (l *BaseEventListener) Stop() error {
	if l.cancel != nil {
		l.cancel()
	}
	l.setRunning(false)
	return nil
}

// Cleanup cleans up resources
func (l *BaseEventListener) Cleanup() {
	l.Stop()
}

// SocketEventListener handles socket-based events (e.g., sway, hyprland sockets)
type SocketEventListener struct {
	*BaseEventListener
	socketPath     string
	socket         net.Conn
	eventHandler   func(event string)
	reconnectDelay time.Duration
	maxRetries     int
}

// NewSocketEventListener creates a new socket event listener
func NewSocketEventListener(socketPath string) *SocketEventListener {
	return &SocketEventListener{
		BaseEventListener: NewBaseEventListener(),
		socketPath:        socketPath,
		reconnectDelay:    5 * time.Second,
		maxRetries:        10,
	}
}

// SetEventHandler sets the event handler
func (l *SocketEventListener) SetEventHandler(handler func(event string)) {
	l.eventHandler = handler
}

// ConnectToSocket connects to the Unix socket
func (l *SocketEventListener) ConnectToSocket() error {
	if l.socketPath == "" {
		return fmt.Errorf("socket path is empty")
	}

	conn, err := net.Dial("unix", l.socketPath)
	if err != nil {
		return fmt.Errorf("failed to connect to socket %s: %w", l.socketPath, err)
	}

	l.socket = conn
	log.Printf("Connected to socket: %s", l.socketPath)
	return nil
}

// Start starts listening for socket events
func (l *SocketEventListener) Start(callback func()) error {
	if l.IsRunning() {
		return fmt.Errorf("socket listener is already running")
	}

	if err := l.ConnectToSocket(); err != nil {
		return fmt.Errorf("failed to connect to socket: %w", err)
	}

	l.setRunning(true)

	go l.listen(callback)

	return nil
}

// listen listens for socket events
func (l *SocketEventListener) listen(callback func()) {
	defer l.Stop()

	buffer := make([]byte, 4096)

	for {
		select {
		case <-l.ctx.Done():
			log.Printf("Socket listener stopped")
			return
		default:
			n, err := l.socket.Read(buffer)
			if err != nil {
				log.Printf("Socket read error: %v", err)

				if l.shouldReconnect() {
					l.reconnect(callback)
					continue
				}

				return
			}

			if n > 0 {
				event := string(buffer[:n])
				l.handleEvent(event, callback)
			}
		}
	}
}

// handleEvent handles an incoming event
func (l *SocketEventListener) handleEvent(event string, callback func()) {
	if l.eventHandler != nil {
		l.eventHandler(event)
	}

	if callback != nil {
		glib.IdleAdd(func() {
			callback()
		})
	}
}

// shouldReconnect determines if we should attempt to reconnect
func (l *SocketEventListener) shouldReconnect() bool {
	return l.maxRetries > 0
}

// reconnect attempts to reconnect to the socket
func (l *SocketEventListener) reconnect(callback func()) {
	for i := 0; i < l.maxRetries; i++ {
		select {
		case <-l.ctx.Done():
			return
		case <-time.After(l.reconnectDelay):
			log.Printf("Attempting to reconnect to socket (attempt %d/%d)...", i+1, l.maxRetries)

			if err := l.ConnectToSocket(); err == nil {
				log.Printf("Successfully reconnected to socket")
				return
			}
		}
	}

	log.Printf("Failed to reconnect after %d attempts", l.maxRetries)
}

// Cleanup cleans up resources
func (l *SocketEventListener) Cleanup() {
	if l.socket != nil {
		l.socket.Close()
		l.socket = nil
	}
	l.BaseEventListener.Cleanup()
}

// IPCEventListener handles IPC-based events
type IPCEventListener struct {
	*BaseEventListener
	messageHandler func(message string)
	ipcChannel     chan string
}

// NewIPCEventListener creates a new IPC event listener
func NewIPCEventListener() *IPCEventListener {
	return &IPCEventListener{
		BaseEventListener: NewBaseEventListener(),
		ipcChannel:        make(chan string, 100),
	}
}

// SetMessageHandler sets the message handler
func (l *IPCEventListener) SetMessageHandler(handler func(message string)) {
	l.messageHandler = handler
}

// Start starts listening for IPC messages
func (l *IPCEventListener) Start(callback func()) error {
	if l.IsRunning() {
		return fmt.Errorf("IPC listener is already running")
	}

	l.setRunning(true)

	go l.listen(callback)

	return nil
}

// listen listens for IPC messages
func (l *IPCEventListener) listen(callback func()) {
	defer l.Stop()

	for {
		select {
		case <-l.ctx.Done():
			log.Printf("IPC listener stopped")
			return
		case message := <-l.ipcChannel:
			l.handleMessage(message, callback)
		}
	}
}

// handleMessage handles an incoming IPC message
func (l *IPCEventListener) handleMessage(message string, callback func()) {
	if l.messageHandler != nil {
		l.messageHandler(message)
	}

	if callback != nil {
		glib.IdleAdd(func() {
			callback()
		})
	}
}

// SendMessage sends a message to the IPC listener
func (l *IPCEventListener) SendMessage(message string) {
	select {
	case l.ipcChannel <- message:
	default:
		log.Printf("IPC channel full, dropping message: %s", message)
	}
}

// SignalEventListener handles signal-based events
type SignalEventListener struct {
	*BaseEventListener
	signal        os.Signal
	signalHandler func(signal os.Signal)
	signalChan    chan os.Signal
}

// NewSignalEventListener creates a new signal event listener
func NewSignalEventListener(signal os.Signal) *SignalEventListener {
	return &SignalEventListener{
		BaseEventListener: NewBaseEventListener(),
		signal:            signal,
		signalChan:        make(chan os.Signal, 1),
	}
}

// SetSignalHandler sets the signal handler
func (l *SignalEventListener) SetSignalHandler(handler func(signal os.Signal)) {
	l.signalHandler = handler
}

// Start starts listening for signals
func (l *SignalEventListener) Start(callback func()) error {
	if l.IsRunning() {
		return fmt.Errorf("signal listener is already running")
	}

	signal.Notify(l.signalChan, l.signal)
	l.setRunning(true)

	go l.listen(callback)

	return nil
}

// listen listens for signals
func (l *SignalEventListener) listen(callback func()) {
	defer l.Stop()

	for {
		select {
		case <-l.ctx.Done():
			log.Printf("Signal listener stopped")
			signal.Stop(l.signalChan)
			return
		case sig := <-l.signalChan:
			l.handleSignal(sig, callback)
		}
	}
}

// handleSignal handles an incoming signal
func (l *SignalEventListener) handleSignal(sig os.Signal, callback func()) {
	if l.signalHandler != nil {
		l.signalHandler(sig)
	}

	if callback != nil {
		glib.IdleAdd(func() {
			callback()
		})
	}
}

// Cleanup cleans up resources
func (l *SignalEventListener) Cleanup() {
	if l.signalChan != nil {
		signal.Stop(l.signalChan)
		close(l.signalChan)
	}
	l.BaseEventListener.Cleanup()
}

// TimerEventListener handles timer-based events
type TimerEventListener struct {
	*BaseEventListener
	interval     time.Duration
	timerHandler func()
	timer        *time.Timer
}

// NewTimerEventListener creates a new timer event listener
func NewTimerEventListener(interval time.Duration) *TimerEventListener {
	return &TimerEventListener{
		BaseEventListener: NewBaseEventListener(),
		interval:          interval,
	}
}

// SetTimerHandler sets the timer handler
func (l *TimerEventListener) SetTimerHandler(handler func()) {
	l.timerHandler = handler
}

// Start starts the timer
func (l *TimerEventListener) Start(callback func()) error {
	if l.IsRunning() {
		return fmt.Errorf("timer listener is already running")
	}

	l.setRunning(true)
	l.timer = time.NewTimer(l.interval)

	go l.listen(callback)

	return nil
}

// listen waits for timer events
func (l *TimerEventListener) listen(callback func()) {
	defer l.Stop()

	for {
		select {
		case <-l.ctx.Done():
			log.Printf("Timer listener stopped")
			return
		case <-l.timer.C:
			l.handleTimerEvent(callback)

			l.timer.Reset(l.interval)
		}
	}
}

// handleTimerEvent handles a timer event
func (l *TimerEventListener) handleTimerEvent(callback func()) {
	if l.timerHandler != nil {
		l.timerHandler()
	}

	if callback != nil {
		glib.IdleAdd(func() {
			callback()
		})
	}
}

// Cleanup cleans up resources
func (l *TimerEventListener) Cleanup() {
	if l.timer != nil {
		l.timer.Stop()
		l.timer = nil
	}
	l.BaseEventListener.Cleanup()
}
