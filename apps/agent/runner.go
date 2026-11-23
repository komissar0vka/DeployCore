package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"math/rand/v2"
	"net/http"
	"time"
)

const inventoryInterval = 6 * time.Hour

type Runner struct {
	client    *Client
	state     State
	save      func(State) error
	heartbeat func() (Heartbeat, error)
	inventory func(context.Context) (Inventory, error)
	log       *log.Logger
	jobs      func(context.Context, State)
}

func (r *Runner) connect(ctx context.Context) (Connection, error) {
	beat, err := r.heartbeat()
	if err != nil {
		return Connection{}, err
	}
	if r.state.PendingToken == "" {
		return r.client.beat(ctx, r.state, beat)
	}

	var reply Connection
	err = r.client.request(ctx, http.MethodPost, "/api/v1/agent/enroll", "", Enrollment{
		InstallationID: r.state.DeviceID, EnrollmentToken: r.state.PendingToken,
		Credential: r.state.Credential, Heartbeat: beat,
	}, &reply)
	if err != nil {
		var status StatusError
		if !errors.As(err, &status) || (status != http.StatusForbidden && status != http.StatusConflict) {
			return Connection{}, err
		}
		// A committed enrollment may have lost its reply before the token expired.
		var retryErr error
		reply, retryErr = r.client.beat(ctx, r.state, beat)
		if retryErr != nil {
			return Connection{}, err
		}
	}
	if !deviceIDPattern.MatchString(reply.DeviceID) {
		return Connection{}, fmt.Errorf("invalid enrollment reply")
	}
	enrolled := r.state
	enrolled.DeviceID = reply.DeviceID
	enrolled.PendingToken = ""
	if err := r.save(enrolled); err != nil {
		return Connection{}, fmt.Errorf("save enrollment: %w", err)
	}
	r.state = enrolled
	r.log.Print("Enrollment completed")
	return reply, nil
}

func backoff(attempt int) time.Duration {
	maxDelay := min(time.Second<<min(attempt, 9), 5*time.Minute)
	return maxDelay/2 + rand.N(maxDelay/2)
}

func (r *Runner) run(ctx context.Context) {
	failures := 0
	var nextInventory time.Time
	var busy <-chan bool
	var jobsDone chan struct{}
	inventoryContext, cancel := context.WithCancel(ctx)
	defer func() {
		cancel()
		if busy != nil {
			<-busy
		}
		if jobsDone != nil {
			<-jobsDone
		}
	}()
	for ctx.Err() == nil {
		reply, err := r.connect(ctx)
		if ctx.Err() != nil {
			return
		}
		if busy != nil {
			select {
			case success := <-busy:
				if success {
					nextInventory = time.Now().Add(inventoryInterval)
				} else {
					nextInventory = time.Now().Add(time.Minute)
				}
				busy = nil
			default:
			}
		}

		var delay time.Duration
		if err != nil {
			r.log.Printf("Connection failed: %v", err)
			delay = backoff(failures)
			if failures < 10 {
				failures++
			}
		} else {
			if failures != 0 {
				r.log.Print("Connection restored")
			}
			failures = 0
			if r.jobs != nil && jobsDone == nil {
				jobsDone = make(chan struct{})
				go func(state State) {
					defer close(jobsDone)
					r.jobs(inventoryContext, state)
				}(r.state)
			}
			seconds := reply.HeartbeatSeconds
			if seconds < 15 || seconds > 3600 {
				seconds = 60
			}
			delay = time.Duration(seconds) * time.Second
			if busy == nil && !time.Now().Before(nextInventory) {
				result := make(chan bool, 1)
				busy = result
				go r.upload(inventoryContext, r.state, result)
			}
		}
		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
		}
	}
}

func (r *Runner) upload(ctx context.Context, state State, result chan<- bool) {
	data, err := r.inventory(ctx)
	if err == nil {
		path := "/api/v1/agent/" + state.DeviceID + "/inventory"
		err = r.client.request(ctx, http.MethodPut, path, state.Credential, data, nil)
	}
	if err != nil && ctx.Err() == nil {
		r.log.Printf("Inventory refresh failed: %v", err)
		path := "/api/v1/agent/" + state.DeviceID + "/issues"
		report := struct {
			Action string `json:"action"`
		}{Action: "inventory_failed"}
		_ = r.client.request(ctx, http.MethodPost, path, state.Credential, report, nil)
	}
	if err == nil {
		r.log.Print("Inventory uploaded")
	}
	result <- err == nil
}
