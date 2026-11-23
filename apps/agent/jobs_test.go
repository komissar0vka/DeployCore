package main

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

func TestJobTransportResumesDurableResult(t *testing.T) {
	ctx := context.Background()
	state := testState(t, "https://deploycore.example")
	assignment := Assignment{
		TargetID: "11111111-1111-4111-8111-111111111111", AttemptID: "22222222-2222-4222-8222-222222222222",
		VersionID: "33333333-3333-4333-8333-333333333333", Operation: "install", Mode: "transport_only",
	}
	var journal JobJournal
	var lock sync.Mutex
	calls := map[string]int{}
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		lock.Lock()
		defer lock.Unlock()
		if r.Header.Get("Authorization") != "Bearer "+state.Credential || r.Method != http.MethodPost {
			t.Error("unexpected credentials or method")
		}
		action := r.URL.Path[strings.LastIndex(r.URL.Path, "/")+1:]
		calls[action]++
		switch action {
		case "poll":
			_ = json.NewEncoder(w).Encode(map[string]Assignment{"assignment": assignment})
		case "ack":
			if journal.Job.AttemptID != assignment.AttemptID {
				t.Error("attempt was acknowledged before persistence")
			}
			if calls[action] == 1 {
				w.WriteHeader(http.StatusServiceUnavailable)
			}
		case "heartbeat":
			_, _ = w.Write([]byte(`{"cancel_requested":true}`))
		case "result":
			var payload struct {
				AttemptID string `json:"attempt_id"`
				Outcome   string `json:"outcome"`
			}
			if err := json.NewDecoder(r.Body).Decode(&payload); err != nil || payload.AttemptID != assignment.AttemptID ||
				payload.Outcome != "cancelled" || journal.Outcome != payload.Outcome {
				t.Error("unexpected or unpersisted terminal result")
			}
			if calls[action] == 1 {
				w.WriteHeader(http.StatusServiceUnavailable)
			}
		default:
			t.Error("unexpected path")
		}
	}))
	defer server.Close()
	client := trustedClient(t, server)
	snapshot := func() JobJournal {
		lock.Lock()
		defer lock.Unlock()
		return journal
	}
	transport := func() *JobTransport {
		return &JobTransport{client: client, state: state, journal: snapshot(), log: log.New(io.Discard, "", 0),
			save: func(next JobJournal) error {
				lock.Lock()
				defer lock.Unlock()
				journal = next
				return nil
			}}
	}
	if err := transport().step(ctx); err == nil || snapshot().Job.AttemptID == "" || snapshot().Outcome != "" {
		t.Fatal("failed ACK did not retain the delivery")
	}
	if err := transport().step(ctx); err == nil || snapshot().Outcome != "cancelled" {
		t.Fatal("failed result did not retain the terminal outcome")
	}
	if err := transport().step(ctx); err != nil || snapshot() != (JobJournal{}) {
		t.Fatalf("replay failed or retained the journal: %v", err)
	}
	lock.Lock()
	defer lock.Unlock()
	if calls["poll"] != 1 || calls["ack"] != 2 || calls["heartbeat"] != 1 || calls["result"] != 2 {
		t.Fatalf("unexpected protocol calls: %v", calls)
	}
}
