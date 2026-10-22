package ui

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"time"
)

const (
	// Age is computed in PowerShell: CreationDate serializes differently
	// between Windows PowerShell and PowerShell 7.
	processQuery = `Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CommandLine,` +
		`@{n='Age';e={[int64]((Get-Date) - $_.CreationDate).TotalSeconds}} | ConvertTo-Json -Compress`
	listenerQuery = `Get-NetTCPConnection -State Listen | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress`
)

// Collect reads the machine through PowerShell, which ships with Windows.
func Collect(ctx context.Context) (Snapshot, error) {
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	procOut, err := powershell(ctx, processQuery)
	if err != nil {
		return Snapshot{}, err
	}
	procs, err := parseWindowsProcesses(procOut)
	if err != nil {
		return Snapshot{}, err
	}
	listenOut, err := powershell(ctx, listenerQuery)
	if err != nil {
		return Snapshot{}, err
	}
	listeners, err := parseWindowsListeners(listenOut)
	if err != nil {
		return Snapshot{}, err
	}
	return Snapshot{
		Processes: procs,
		Listeners: listeners,
		Chromium:  findChromium("windows", exec.LookPath, fileExists, os.Getenv),
	}, nil
}

func powershell(ctx context.Context, query string) (string, error) {
	out, err := exec.CommandContext(ctx, "powershell", "-NoProfile", "-NonInteractive", "-Command", query).Output()
	if err != nil {
		return "", fmt.Errorf("powershell %q: %w", query, err)
	}
	return string(out), nil
}
