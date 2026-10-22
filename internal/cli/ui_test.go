package cli

import (
	"strings"
	"testing"
)

func TestUIWithoutACommandSaysWhatExists(t *testing.T) {
	for _, args := range [][]string{{"ui"}, {"ui", "fix"}} {
		code, _, stderr := run(t, args...)
		if code != 2 {
			t.Errorf("%q: exit %d, want 2", args, code)
		}
		if !strings.Contains(stderr, "jacazul ui doctor") {
			t.Errorf("%q: stderr %q does not name the doctor", args, stderr)
		}
	}
}

// The doctor reads the real machine here, so only its contract is
// checked: it answers with a report and an exit status that says whether
// anything needs the operator, never a failure of its own.
func TestUIDoctorReportsOnTheRealMachine(t *testing.T) {
	code, stdout, stderr := run(t, "ui", "doctor")
	if code != 0 && code != 1 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if !strings.HasPrefix(stdout, "🐊 UI DOCTOR") {
		t.Errorf("stdout %q has no report header", stdout)
	}
}
