package main

import (
	_ "embed"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"unsafe"

	"golang.org/x/sys/windows"
)

//go:embed setup.ps1
var setupScript string

func showSetupError(message string) {
	body, _ := windows.UTF16PtrFromString(message)
	title := windows.StringToUTF16Ptr("DeployCore Agent")
	_, _, _ = windows.NewLazySystemDLL("user32.dll").NewProc("MessageBoxW").Call(
		0, uintptr(unsafe.Pointer(body)), uintptr(unsafe.Pointer(title)), 0x10,
	)
}

func launchSetup() error {
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	path, err := windows.UTF16PtrFromString(exe)
	if err != nil {
		return err
	}
	return windows.ShellExecute(0, windows.StringToUTF16Ptr("runas"), path,
		windows.StringToUTF16Ptr("setup"), nil, windows.SW_HIDE)
}

func runSetup() error {
	if !windows.GetCurrentProcessToken().IsElevated() {
		return fmt.Errorf("start DeployCore Agent with administrator permissions")
	}
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	system, err := windows.GetSystemDirectory()
	if err != nil {
		return err
	}
	powerShell := filepath.Join(system, "WindowsPowerShell", "v1.0", "powershell.exe")
	cmd := exec.Command(powerShell, "-NoLogo", "-NoProfile", "-STA", "-EncodedCommand", encodedScript(setupScript))
	cmd.Env = append(os.Environ(), "DEPLOYCORE_SETUP_EXE="+exe)
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.CREATE_NO_WINDOW}
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("could not open the setup wizard: %w\n%s", err, output)
	}
	return nil
}
