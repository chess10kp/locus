package core

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"strings"
	"sync/atomic"
	"time"

	"github.com/chess10kp/locus/internal/config"
	"github.com/gotk3/gotk3/glib"
)

type IPCServer struct {
	app           *App
	config        *config.Config
	server        *net.UnixListener
	running       bool
	ctx           context.Context
	cancel        context.CancelFunc
	callbacks     atomic.Int64
	callbacksExec atomic.Int64
}

func NewIPCServer(app *App, cfg *config.Config) *IPCServer {
	ctx, cancel := context.WithCancel(context.Background())
	return &IPCServer{
		app:     app,
		config:  cfg,
		running: false,
		ctx:     ctx,
		cancel:  cancel,
	}
}

func (s *IPCServer) Start() error {
	if s.running {
		return fmt.Errorf("IPC server already running")
	}

	// Remove existing socket file if it exists
	socketPath := s.config.SocketPath
	if _, err := os.Stat(socketPath); err == nil {
		os.Remove(socketPath)
	}

	// Create Unix socket listener
	listener, err := net.Listen("unix", socketPath)
	if err != nil {
		return fmt.Errorf("failed to create socket listener: %w", err)
	}

	s.server = listener.(*net.UnixListener)
	s.running = true

	log.Printf("IPC server listening on %s", socketPath)

	// Start accepting connections
	go s.acceptConnections(s.ctx)

	// Start callback monitoring
	go s.monitorCallbacks(s.ctx)

	return nil
}

func (s *IPCServer) monitorCallbacks(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	lastExecCount := s.callbacksExec.Load()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			scheduled := s.callbacks.Load()
			executed := s.callbacksExec.Load()
			if executed > lastExecCount {
				lastExecCount = executed
			} else if scheduled > executed && scheduled-executed > 3 {
				// More than 3 callbacks pending without execution
				log.Printf("[IPC] WARNING: %d callbacks scheduled but only %d executed (diff=%d), GTK main loop may be blocked!",
					scheduled, executed, scheduled-executed)
			}
		}
	}
}

func (s *IPCServer) acceptConnections(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		if !s.running {
			return
		}

		conn, err := s.server.Accept()
		if err != nil {
			if s.running {
				log.Printf("Error accepting connection: %v", err)
			}
			continue
		}

		unixConn, ok := conn.(*net.UnixConn)
		if !ok {
			log.Printf("Not a Unix connection")
			conn.Close()
			continue
		}

		go s.handleConnection(ctx, unixConn)
	}
}

func (s *IPCServer) handleConnection(ctx context.Context, conn *net.UnixConn) {
	defer conn.Close()

	type result struct {
		message string
		err     error
	}

	resultCh := make(chan result, 1)

	// Read message in goroutine with timeout
	go func() {
		buf := make([]byte, 1024)
		n, err := conn.Read(buf)
		if err != nil {
			resultCh <- result{err: err}
			return
		}
		message := strings.TrimSpace(string(buf[:n]))
		resultCh <- result{message: message}
	}()

	select {
	case res := <-resultCh:
		if res.err != nil {
			log.Printf("Error reading from connection: %v", res.err)
			return
		}
		log.Printf("Received IPC message: %s", res.message)
		s.handleMessage(res.message)
	case <-ctx.Done():
		log.Printf("IPC connection handling cancelled")
		return
	}
}

func (s *IPCServer) handleMessage(message string) {
	if message == "launcher" {
		log.Printf("[IPC] Handling launcher message - app=%v", s.app != nil)
		if s.app == nil {
			log.Printf("[IPC] ERROR: app is nil!")
			return
		}
		log.Printf("[IPC] About to call glib.IdleAdd")
		s.callbacks.Add(1)
		result := glib.IdleAdd(func() {
			s.callbacksExec.Add(1)
			log.Printf("[IPC] IdleAdd callback executing (scheduled: %d, executed: %d)",
				s.callbacks.Load(), s.callbacksExec.Load())
			// Toggle launcher instead of just showing
			if err := s.app.ToggleLauncher(); err != nil {
				log.Printf("Failed to toggle launcher: %v", err)
			}
			log.Printf("[IPC] ToggleLauncher completed")
		})
		log.Printf("[IPC] glib.IdleAdd returned: %v", result)

		// Fallback: if callback doesn't execute in 1 second, try direct call
		go func() {
			time.Sleep(1 * time.Second)
			scheduled := s.callbacks.Load()
			executed := s.callbacksExec.Load()
			if scheduled > executed {
				log.Printf("[IPC] WARNING: Callback not executed after 1s (scheduled: %d, executed: %d), attempting direct call",
					scheduled, executed)
				s.callbacksExec.Add(1)
				if err := s.app.ToggleLauncher(); err != nil {
					log.Printf("[IPC] Direct ToggleLauncher call failed: %v", err)
				}
			}
		}()
	} else if message == "hide" {
		glib.IdleAdd(func() {
			if err := s.app.HideLauncher(); err != nil {
				log.Printf("Failed to hide launcher: %v", err)
			}
		})
	} else if message == "lock" {
		glib.IdleAdd(func() {
			if err := s.app.ShowLockScreen(); err != nil {
				log.Printf("Failed to show lock screen: %v", err)
			}
		})
	} else if strings.HasPrefix(message, "statusbar:") {
		// Handle statusbar messages
		if s.app.statusBar != nil {
			cmd := strings.TrimPrefix(message, "statusbar:")
			log.Printf("[IPC] Forwarding statusbar message: %s", cmd)
			glib.IdleAdd(func() {
				if err := s.app.statusBar.HandleIPC(cmd); err != nil {
					log.Printf("Failed to handle statusbar IPC: %v", err)
				}
			})
		} else {
			log.Printf("[IPC] StatusBar is nil, cannot handle message: %s", message)
		}
	} else if strings.HasPrefix(message, "status:") {
		// Handle status messages from hooks/launchers
		statusMsg := strings.TrimPrefix(message, "status:")
		glib.IdleAdd(func() {
			if s.app.statusBar != nil {
				// TODO: Implement status message display
				log.Printf("Status message: %s", statusMsg)
			}
		})
	} else if strings.HasPrefix(message, "launcher:refresh:") {
		// Handle launcher refresh requests
		launcherName := strings.TrimPrefix(message, "launcher:refresh:")
		glib.IdleAdd(func() {
			if s.app.launcher != nil && s.app.launcher.registry != nil {
				if err := s.app.launcher.registry.RefreshLauncher(launcherName); err != nil {
					log.Printf("Failed to refresh launcher '%s': %v", launcherName, err)
				}
			}
		})
	}
}

func (s *IPCServer) Stop() error {
	if !s.running {
		return nil
	}

	s.running = false
	s.cancel() // Cancel context to stop all goroutines

	if s.server != nil {
		s.server.Close()
	}

	// Remove socket file
	socketPath := s.config.SocketPath
	if _, err := os.Stat(socketPath); err == nil {
		os.Remove(socketPath)
	}

	log.Println("IPC server stopped")
	return nil
}
