package cli

import (
	"context"
	"fmt"
	"io"
	"runtime"

	"github.com/jacazul-ai/launcher/internal/ui"
)

// runUI holds the UI verification commands. The doctor exits 0 when clean,
// 1 when something needs the operator, and 2 when it could not look; a
// usage error is a 2 as well, so scripts never read it as a finding.
func runUI(args []string, stdout, stderr io.Writer) int {
	if len(args) != 1 || args[0] != "doctor" {
		fmt.Fprintln(stderr, "❌ jacazul ui: the only command is 'jacazul ui doctor' (read-only audit of browser automation servers)")
		return 2
	}
	s, err := ui.Collect(context.Background())
	if err != nil {
		fmt.Fprintf(stderr, "❌ jacazul ui doctor: %v\n", err)
		return 2
	}
	r := ui.Diagnose(s)
	ui.Write(stdout, r, runtime.GOOS)
	if r.Clean() {
		return 0
	}
	return 1
}
