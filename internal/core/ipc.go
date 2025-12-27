package core

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"strings"

	"github.com/gotk3/gotk3/glib"
	"github.com/sigma/locus-go/internal/config"
)

type IPCServer struct {
	app     *App
	config  *config.Config
	server  *net.UnixListener
	running bool
	ctx     context.Context
	cancel  context.CancelFunc
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

	return nil
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
		glib.IdleAdd(func() {
			if err := s.app.PresentLauncher(); err != nil {
				log.Printf("Failed to present launcher: %v", err)
			}
		})
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
