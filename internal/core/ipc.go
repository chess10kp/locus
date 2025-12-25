package core

import (
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
}

func NewIPCServer(app *App, cfg *config.Config) *IPCServer {
	return &IPCServer{
		app:     app,
		config:  cfg,
		running: false,
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
	go s.acceptConnections()

	return nil
}

func (s *IPCServer) acceptConnections() {
	for s.running {
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

		go s.handleConnection(unixConn)
	}
}

func (s *IPCServer) handleConnection(conn *net.UnixConn) {
	defer conn.Close()

	buf := make([]byte, 1024)
	n, err := conn.Read(buf)
	if err != nil {
		log.Printf("Error reading from connection: %v", err)
		return
	}

	message := strings.TrimSpace(string(buf[:n]))
	log.Printf("Received IPC message: %s", message)

	s.handleMessage(message)
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
	} else if strings.HasPrefix(message, "statusbar:") {
		// Handle statusbar messages
		if s.app.statusBar != nil {
			cmd := strings.TrimPrefix(message, "statusbar:")
			glib.IdleAdd(func() {
				if err := s.app.statusBar.HandleIPC(cmd); err != nil {
					log.Printf("Failed to handle statusbar IPC: %v", err)
				}
			})
		}
	}
}

func (s *IPCServer) Stop() error {
	if !s.running {
		return nil
	}

	s.running = false

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
