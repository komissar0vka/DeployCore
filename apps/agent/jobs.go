package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"time"
)

type Assignment struct {
	TargetID  string `json:"target_id"`
	AttemptID string `json:"attempt_id"`
	VersionID string `json:"version_id"`
	Operation string `json:"operation"`
	Mode      string `json:"mode"`
}

func (a Assignment) valid() bool {
	return a.Mode == "transport_only" && deviceIDPattern.MatchString(a.TargetID) &&
		deviceIDPattern.MatchString(a.AttemptID) && deviceIDPattern.MatchString(a.VersionID) &&
		(a.Operation == "install" || a.Operation == "uninstall")
}

type JobJournal struct {
	Server   string     `json:"server"`
	DeviceID string     `json:"device_id"`
	Job      Assignment `json:"job"`
	Outcome  string     `json:"outcome,omitempty"`
}

type JobTransport struct {
	client  *Client
	state   State
	journal JobJournal
	save    func(JobJournal) error
	log     *log.Logger
}

func (t *JobTransport) persist(next JobJournal) error {
	if err := t.save(next); err != nil {
		return fmt.Errorf("save deployment journal: %w", err)
	}
	t.journal = next
	return nil
}

func (t *JobTransport) run(ctx context.Context) {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()
	for ctx.Err() == nil {
		if err := t.step(ctx); err != nil && ctx.Err() == nil {
			var status StatusError
			if !errors.As(err, &status) || status != http.StatusNotFound {
				t.log.Printf("Deployment transport: %v", err)
			}
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

func (t *JobTransport) step(ctx context.Context) error {
	base := "/api/v1/agent/" + t.state.DeviceID + "/jobs/"
	if t.journal.Job.AttemptID == "" {
		var poll struct {
			Assignment *Assignment `json:"assignment"`
		}
		if err := t.client.request(ctx, http.MethodPost, base+"poll", t.state.Credential, nil, &poll); err != nil {
			return err
		}
		if poll.Assignment == nil {
			return nil
		}
		if !poll.Assignment.valid() {
			return fmt.Errorf("unsupported deployment assignment")
		}
		if err := t.persist(JobJournal{Server: t.state.Server, DeviceID: t.state.DeviceID, Job: *poll.Assignment}); err != nil {
			return err
		}
		t.log.Printf("Deployment received: %s", poll.Assignment.TargetID)
	}

	next := t.journal
	if next.DeviceID != t.state.DeviceID || next.Server != t.state.Server || !next.Job.valid() ||
		(next.Outcome != "" && next.Outcome != "not_executed" && next.Outcome != "cancelled") {
		return fmt.Errorf("invalid deployment journal for this agent")
	}
	path := base + next.Job.TargetID + "/"
	lease := struct {
		AttemptID string `json:"attempt_id"`
	}{next.Job.AttemptID}

	if next.Outcome == "" {
		if err := t.client.request(ctx, http.MethodPost, path+"ack", t.state.Credential, lease, nil); err != nil {
			var status StatusError
			if errors.As(err, &status) && status == http.StatusConflict {
				// The server rejects only a closed, unknown, or expired unacknowledged delivery.
				return t.persist(JobJournal{})
			}
			return err
		}
		var heartbeat struct {
			CancelRequested bool `json:"cancel_requested"`
		}
		if err := t.client.request(ctx, http.MethodPost, path+"heartbeat", t.state.Credential, lease, &heartbeat); err != nil {
			return err
		}
		next.Outcome = "not_executed"
		if heartbeat.CancelRequested {
			next.Outcome = "cancelled"
		}
		if err := t.persist(next); err != nil {
			return err
		}
	}
	result := struct {
		AttemptID string `json:"attempt_id"`
		Outcome   string `json:"outcome"`
	}{next.Job.AttemptID, next.Outcome}
	if err := t.client.request(ctx, http.MethodPost, path+"result", t.state.Credential, result, nil); err != nil {
		return err
	}
	t.log.Printf("Deployment result accepted: %s %s", next.Job.TargetID, next.Outcome)
	return t.persist(JobJournal{})
}
