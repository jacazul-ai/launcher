package ui

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"time"
)

// Collect reads the machine through ps and lsof, both part of macOS.
func Collect(ctx context.Context) (Snapshot, error) {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	ps, err := exec.CommandContext(ctx, "ps", "-axo", "pid=,ppid=,etime=,command=").Output()
	if err != nil {
		return Snapshot{}, fmt.Errorf("ps: %w", err)
	}
	// lsof exits 1 when nothing listens; an exit status is still an answer.
	lsof, err := exec.CommandContext(ctx, "lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-Fpn").Output()
	var exit *exec.ExitError
	if err != nil && !errors.As(err, &exit) {
		return Snapshot{}, fmt.Errorf("lsof: %w", err)
	}
	return Snapshot{
		Processes: parsePS(string(ps)),
		Listeners: parseLsof(string(lsof)),
		Chromium:  findChromium("darwin", exec.LookPath, fileExists, os.Getenv),
	}, nil
}
