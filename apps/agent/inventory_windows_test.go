package main

import (
	"context"
	"testing"
)

func TestWindowsInventory(t *testing.T) {
	beat, err := collectHeartbeat()
	if err != nil {
		t.Fatal(err)
	}
	if beat.Hostname == "" || beat.OSVersion == "" {
		t.Fatal("missing Windows hostname or version")
	}
	inventory, err := collectInventory(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(inventory.Hardware.CPUs) == 0 || inventory.Hardware.RAM == 0 || inventory.Hardware.OS.Build == "" {
		t.Fatal("missing local Windows inventory")
	}
}

func TestWindowsProtectedState(t *testing.T) {
	directory := t.TempDir()
	initial := testState(t, "https://deploycore.example")
	if err := saveState(directory, initial); err != nil {
		t.Fatal(err)
	}
	result, err := loadState(directory)
	if err != nil {
		t.Fatal(err)
	}
	if result.DeviceID != initial.DeviceID || result.Credential != initial.Credential {
		t.Fatal("protected state did not survive reload")
	}
}
