package main

import (
	"bytes"
	"context"
	"encoding/json"
	"encoding/pem"
	"errors"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func trustedClient(t *testing.T, server *httptest.Server) *Client {
	t.Helper()
	ca := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: server.Certificate().Raw})
	client, err := newClient(server.URL, ca)
	if err != nil {
		t.Fatal(err)
	}
	return client
}

func fakeHeartbeat() (Heartbeat, error) {
	return Heartbeat{Hostname: "WORKSTATION", IPs: []string{}, OSVersion: "Windows 10.0.26100", AgentVersion: version}, nil
}

func testState(t *testing.T, server string) State {
	t.Helper()
	id, err := installationID()
	if err != nil {
		t.Fatal(err)
	}
	credential, err := randomCredential()
	if err != nil {
		t.Fatal(err)
	}
	return State{Server: server, DeviceID: id, Credential: credential}
}

func TestTLSVerificationAndRedirects(t *testing.T) {
	var redirected atomic.Bool
	target := httptest.NewTLSServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		redirected.Store(true)
	}))
	defer target.Close()
	server := httptest.NewTLSServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		http.Redirect(response, request, target.URL, http.StatusTemporaryRedirect)
	}))
	defer server.Close()
	if _, err := newClient("http://example.invalid", nil); err == nil {
		t.Fatal("accepted HTTP")
	}
	untrusted, err := newClient(server.URL, nil)
	if err != nil {
		t.Fatal(err)
	}
	if err := untrusted.request(context.Background(), "GET", "/", "", nil, nil); err == nil {
		t.Fatal("accepted an untrusted server")
	}
	trusted := trustedClient(t, server)
	var status StatusError
	err = trusted.request(context.Background(), "GET", "/", "secret", nil, nil)
	if !errors.As(err, &status) || status != http.StatusTemporaryRedirect || redirected.Load() {
		t.Fatalf("unexpected redirect result: %v", err)
	}
}

func TestEnrollmentRecoversLostResponseWithoutNewIdentity(t *testing.T) {
	state := testState(t, "")
	state.PendingToken = state.Credential
	server := httptest.NewTLSServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		if request.URL.Path == "/api/v1/agent/enroll" {
			var data Enrollment
			if err := json.NewDecoder(request.Body).Decode(&data); err != nil ||
				data.InstallationID != state.DeviceID || data.Credential != state.Credential {
				t.Error("unexpected enrollment identity")
			}
			response.WriteHeader(http.StatusForbidden)
			return
		}
		if request.Header.Get("Authorization") != "Bearer "+state.Credential {
			t.Error("heartbeat did not retain the same credential")
		}
		json.NewEncoder(response).Encode(Connection{DeviceID: state.DeviceID, HeartbeatSeconds: 60})
	}))
	defer server.Close()
	var saved State
	runner := Runner{client: trustedClient(t, server), state: state, heartbeat: fakeHeartbeat,
		save: func(next State) error { saved = next; return nil }, log: log.New(io.Discard, "", 0)}
	if _, err := runner.connect(context.Background()); err != nil {
		t.Fatal(err)
	}
	if saved.DeviceID != state.DeviceID || saved.Credential != state.Credential || saved.PendingToken != "" {
		t.Fatal("enrollment was not persisted correctly")
	}
}

func TestReconnectAndInventoryAfterTemporaryOutage(t *testing.T) {
	state := testState(t, "")
	var attempts atomic.Int32
	uploaded := make(chan struct{})
	var once sync.Once
	server := httptest.NewTLSServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		if request.Header.Get("Authorization") != "Bearer "+state.Credential {
			t.Error("expected agent authorization")
		}
		if strings.HasSuffix(request.URL.Path, "/inventory") {
			var inventory Inventory
			if err := json.NewDecoder(request.Body).Decode(&inventory); err != nil || len(inventory.Software) != 1 {
				t.Error("invalid inventory payload")
			}
			response.WriteHeader(http.StatusNoContent)
			once.Do(func() { close(uploaded) })
			return
		}
		if attempts.Add(1) == 1 {
			response.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		json.NewEncoder(response).Encode(Connection{DeviceID: state.DeviceID, HeartbeatSeconds: 60})
	}))
	defer server.Close()
	var logs bytes.Buffer
	runner := Runner{client: trustedClient(t, server), state: state, heartbeat: fakeHeartbeat,
		inventory: func(context.Context) (Inventory, error) {
			return Inventory{Software: []Software{{Name: "Example"}}}, nil
		}, log: log.New(&logs, "", 0)}
	ctx, cancel := context.WithTimeout(context.Background(), 6*time.Second)
	defer cancel()
	done := make(chan struct{})
	go func() { defer close(done); runner.run(ctx) }()
	select {
	case <-uploaded:
	case <-ctx.Done():
		t.Error("agent did not reconnect and upload inventory")
	}
	cancel()
	<-done
	if !strings.Contains(logs.String(), "Connection restored") || attempts.Load() != 2 {
		t.Fatal("expected one failed heartbeat followed by recovery")
	}
}

func TestExponentialBackoffBounds(t *testing.T) {
	for _, attempt := range []int{0, 1, 4, 9, 20} {
		maxDelay := min(time.Second<<min(attempt, 9), 5*time.Minute)
		for range 10 {
			if delay := backoff(attempt); delay < maxDelay/2 || delay >= maxDelay {
				t.Fatalf("attempt %d: unexpected backoff %s", attempt, delay)
			}
		}
	}
}

func TestHTTPSReadinessRequiresExpectedResponse(t *testing.T) {
	for _, test := range []struct {
		name string
		code int
		body string
		ok   bool
	}{
		{"ready", 200, `{"status":"ok"}`, true},
		{"other application", 200, "<html>sign in</html>", false},
		{"wrong status", 200, `{"status":"unavailable"}`, false},
		{"unavailable", 503, `{"status":"unavailable"}`, false},
	} {
		t.Run(test.name, func(t *testing.T) {
			server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/api/health/ready" || r.Header.Get("Authorization") != "" {
					t.Error("readiness probe used an unexpected endpoint or credential")
				}
				w.WriteHeader(test.code)
				_, _ = w.Write([]byte(test.body))
			}))
			defer server.Close()
			err := trustedClient(t, server).checkReady(context.Background())
			if (err == nil) != test.ok {
				t.Fatalf("unexpected readiness result: %v", err)
			}
		})
	}
}
