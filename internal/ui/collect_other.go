//go:build !linux && !darwin && !windows

package ui

import (
	"context"
	"fmt"
	"runtime"
)

// Collect has no source on this system yet.
func Collect(context.Context) (Snapshot, error) {
	return Snapshot{}, fmt.Errorf("no process source for %s yet; run the manual audit in ui-expert references/browser-safety.md", runtime.GOOS)
}
