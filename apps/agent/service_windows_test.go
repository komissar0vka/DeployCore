package main

import (
	"encoding/json"
	"encoding/pem"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"golang.org/x/sys/windows"
	"golang.org/x/sys/windows/svc"
	"golang.org/x/sys/windows/svc/mgr"
)

func TestPackagedAgentService(t *testing.T) {
	exe := os.Getenv("DEPLOYCORE_TEST_PACKAGED_AGENT")
	if exe == "" {
		t.Skip("set DEPLOYCORE_TEST_PACKAGED_AGENT on a clean elevated Windows runner")
	}
	if !windows.GetCurrentProcessToken().IsElevated() {
		t.Fatal("test requires administrator rights")
	}
	directory, err := agentDirectory()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Lstat(directory); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("test requires a clean host without DeployCore service files")
	}
	manager, err := mgr.Connect()
	if err != nil {
		t.Fatal(err)
	}
	defer manager.Disconnect()
	if existing, err := manager.OpenService(serviceName); !errors.Is(err, windows.ERROR_SERVICE_DOES_NOT_EXIST) {
		if existing != nil {
			existing.Close()
		}
		t.Fatal("test requires a clean host without a DeployCore service")
	}

	token, err := randomCredential()
	if err != nil {
		t.Fatal(err)
	}
	var mu sync.Mutex
	var id, credential string
	enrolled, inventory, pulse := make(chan struct{}, 1), make(chan struct{}, 1), make(chan struct{}, 1)
	signal := func(event chan struct{}) {
		select {
		case event <- struct{}{}:
		default:
		}
	}
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/health/ready":
			_, _ = w.Write([]byte(`{"status":"ok"}`))
		case "/api/v1/agent/enroll":
			var input Enrollment
			if r.Method != http.MethodPost || json.NewDecoder(r.Body).Decode(&input) != nil ||
				input.EnrollmentToken != token || !deviceIDPattern.MatchString(input.InstallationID) ||
				!validToken(input.Credential) || input.Heartbeat.Hostname == "" || input.Heartbeat.AgentVersion != version {
				w.WriteHeader(http.StatusBadRequest)
				return
			}
			id, credential = input.InstallationID, input.Credential
			signal(enrolled)
			_ = json.NewEncoder(w).Encode(Connection{DeviceID: id, HeartbeatSeconds: 60})
		default:
			if credential == "" || r.Header.Get("Authorization") != "Bearer "+credential {
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			switch r.URL.Path {
			case "/api/v1/agent/" + id + "/inventory":
				var data Inventory
				if r.Method != http.MethodPut || json.NewDecoder(r.Body).Decode(&data) != nil ||
					len(data.Hardware.CPUs) == 0 || data.Hardware.RAM == 0 {
					w.WriteHeader(http.StatusBadRequest)
					return
				}
				w.WriteHeader(http.StatusNoContent)
				signal(inventory)
			case "/api/v1/agent/" + id + "/heartbeat":
				_ = json.NewEncoder(w).Encode(Connection{DeviceID: id, HeartbeatSeconds: 60})
				signal(pulse)
			default:
				w.WriteHeader(http.StatusNotFound)
			}
		}
	}))
	defer server.Close()

	file := filepath.Join(t.TempDir(), "trust.pem")
	if err := os.WriteFile(file, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: server.Certificate().Raw}), 0600); err != nil {
		t.Fatal(err)
	}
	rejected := exec.Command(exe, "install", "--server", server.URL)
	rejected.Stdin = strings.NewReader(token)
	if err := rejected.Run(); err == nil {
		t.Fatal("installer accepted an untrusted certificate")
	}
	t.Cleanup(func() {
		_ = exec.Command(exe, "uninstall").Run()
		if err := os.RemoveAll(directory); err != nil {
			t.Error(err)
		}
	})
	install := exec.Command(exe, "install", "--server", server.URL, "--ca", file)
	install.Stdin = strings.NewReader(token)
	if output, err := install.CombinedOutput(); err != nil {
		t.Fatalf("install failed: %v: %s", err, output)
	}
	wait := func(label string, event <-chan struct{}) {
		t.Helper()
		select {
		case <-event:
		case <-time.After(55 * time.Second):
			t.Fatalf("agent did not send %s", label)
		}
	}
	wait("enrollment", enrolled)
	wait("inventory", inventory)
	service, err := manager.OpenService(serviceName)
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	config, err := service.Config()
	if err != nil || config.StartType != mgr.StartAutomatic {
		t.Fatal("service is not configured to start automatically")
	}
	if err := stopService(service); err != nil {
		t.Fatal(err)
	}
	select {
	case <-pulse:
	default:
	}
	if status, err := service.Query(); err != nil || status.State != svc.Stopped {
		t.Fatal("service did not stop")
	}
	if err := service.Start(); err != nil {
		t.Fatal(err)
	}
	wait("heartbeat after restart with the original credential", pulse)
	select {
	case <-enrolled:
		t.Fatal("service enrolled again after restart")
	default:
	}
}
