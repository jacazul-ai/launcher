package ui

import (
	"context"
	"os"
	"os/exec"
)

// Collect reads the machine through /proc, which needs no external tool.
func Collect(context.Context) (Snapshot, error) {
	s, err := readProc("/proc")
	if err != nil {
		return Snapshot{}, err
	}
	s.Chromium = findChromium("linux", exec.LookPath, fileExists, os.Getenv)
	return s, nil
}
