package cli

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/jacazul-ai/flow"
)

func TestFlowSessionListReadsTheProjectLanes(t *testing.T) {
	l := setup(t)
	t.Setenv("JACAZUL_SESSION_ID", "bbbbbbbb")
	id := filepath.Base(filepath.Dir(l.project)) + "_" + filepath.Base(l.project)
	dir := filepath.Join(l.home, ".jacazul-ai", ".task", id)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	for name, content := range map[string]string{
		"focus-bbbbbbbb.json":      `{"focused_plan": "jacazul-launcher", "focused_task_uuid": "454bc8a1-4a64"}`,
		"session-note-bbbbbbbb.md": "",
	} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}

	code, stdout, stderr := run(t, "flow", "session", "list")
	if code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	lines := strings.Split(strings.TrimSuffix(stdout, "\n"), "\n")
	if len(lines) != 3 {
		t.Fatalf("want header, rule and one lane:\n%s", stdout)
	}
	if !strings.HasPrefix(lines[0], "SESSION  ") || !strings.HasSuffix(lines[0], "HANDOFF") {
		t.Errorf("header %q", lines[0])
	}
	for _, col := range []struct{ header, value string }{
		{"PLAN", "jacazul-launcher"}, {"TASK", "454bc8a1"}, {"STATUS", "active"},
	} {
		if h, v := strings.Index(lines[0], col.header), strings.Index(lines[2], col.value); h != v {
			t.Errorf("%s starts at %d in the header and %d in the lane", col.header, h, v)
		}
	}
	fields := strings.Fields(lines[2])
	want := []string{"bbbbbbbb", "*", "jacazul-launcher", "454bc8a1"}
	for i, w := range want {
		if i >= len(fields) || fields[i] != w {
			t.Fatalf("lane %q, want it to start with %q", lines[2], want)
		}
	}
	if !strings.HasSuffix(lines[2], "active  unread") {
		t.Errorf("lane %q lacks status and handoff", lines[2])
	}
}

// The jacazul options in front of flow pick the project, home and current
// session, as they do in front of a harness; explicit options beat TASKDATA.
func TestFlowSessionListFollowsTheJacazulOptions(t *testing.T) {
	for name, tc := range map[string]struct {
		args []string
		vars map[string]string
	}{
		"flags": {args: []string{"--project", "sandbox_x", "--session", "dddddddd"}},
		"environment": {vars: map[string]string{
			"JACAZUL_PROJECT": "sandbox_x", "JACAZUL_SESSION": "dddddddd",
		}},
	} {
		t.Run(name, func(t *testing.T) {
			l := setup(t)
			t.Setenv("TASKDATA", t.TempDir())
			for k, v := range tc.vars {
				t.Setenv(k, v)
			}
			home := filepath.Join(l.home, "sandbox-home")
			dir := filepath.Join(home, ".task", "sandbox_x")
			if err := os.MkdirAll(dir, 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(dir, "focus-dddddddd.json"), []byte("{}"), 0o644); err != nil {
				t.Fatal(err)
			}
			args := append([]string{"--home", home}, tc.args...)
			code, stdout, stderr := run(t, append(args, "flow", "session", "list")...)
			if code != 0 {
				t.Fatalf("exit %d, stderr %q", code, stderr)
			}
			if !strings.Contains(stdout, "dddddddd *") {
				t.Errorf("current sandbox lane missing:\n%s", stdout)
			}
		})
	}
}

func TestFlowSessionListHonorsTaskData(t *testing.T) {
	setup(t)
	dir := t.TempDir()
	t.Setenv("TASKDATA", dir)
	if err := os.WriteFile(filepath.Join(dir, "focus-cccccccc.json"), []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}
	_, stdout, _ := run(t, "flow", "session", "list")
	if !strings.Contains(stdout, "cccccccc    -") {
		t.Errorf("TASKDATA lane missing:\n%s", stdout)
	}
}

func TestFlowSessionListWithoutLanes(t *testing.T) {
	setup(t)
	code, stdout, _ := run(t, "flow", "session", "list")
	if code != 0 || stdout != "ℹ No independent sessions found.\n" {
		t.Fatalf("exit %d, stdout %q", code, stdout)
	}
}

// engineCall is what one flow.Run call received.
type engineCall struct {
	ctx     context.Context
	args    []string
	env     flow.Env
	streams flow.Streams
}

// fakeEngine replaces flow.Run for the test. The fake writes one line to
// each output stream and returns code.
func fakeEngine(t *testing.T, code int) *[]engineCall {
	t.Helper()
	var calls []engineCall
	saved := runEngine
	runEngine = func(ctx context.Context, args []string, env flow.Env, streams flow.Streams) int {
		calls = append(calls, engineCall{ctx, args, env, streams})
		fmt.Fprintln(streams.Stdout, "engine out")
		fmt.Fprintln(streams.Stderr, "ERROR: schema 9 is newer than 4\nACTION: upgrade jacazul")
		return code
	}
	t.Cleanup(func() { runEngine = saved })
	return &calls
}

func TestFlowMigrateRunsTheEmbeddedEngine(t *testing.T) {
	l := setup(t)
	calls := fakeEngine(t, 3)
	home := t.TempDir()

	code, stdout, stderr := run(t, "--home", home, "--project", "sandbox_x", "--session", "dddddddd",
		"flow", "migrate", "taskwarrior", "--dry-run")
	if code != 3 {
		t.Errorf("exit %d, want the engine's 3", code)
	}
	if stdout != "engine out\n" {
		t.Errorf("stdout %q, want the engine's output unchanged", stdout)
	}
	if stderr != "ERROR: schema 9 is newer than 4\nACTION: upgrade jacazul\n" {
		t.Errorf("stderr %q, want the engine's guidance unchanged", stderr)
	}
	if len(*calls) != 1 {
		t.Fatalf("engine ran %d times, want once with no retry", len(*calls))
	}
	call := (*calls)[0]
	if want := []string{"migrate", "taskwarrior", "--dry-run"}; !slices.Equal(call.args, want) {
		t.Errorf("args %q, want %q", call.args, want)
	}
	// --home names the legacy runtime home; the flow database lives under
	// ~/.jacazul whatever it says.
	flowHome := filepath.Join(l.home, ".jacazul")
	want := flow.Env{
		ProjectID:    "sandbox_x",
		SessionID:    "dddddddd",
		Home:         flowHome,
		DatabasePath: filepath.Join(flowHome, "projects", "sandbox_x", "flow.sqlite3"),
	}
	if call.env != want {
		t.Errorf("env %+v, want %+v", call.env, want)
	}
	if call.ctx == nil {
		t.Error("no context passed")
	}
	if call.streams.Stdin != os.Stdin {
		t.Error("stdin is not the process stdin")
	}
}

// The pinned engine itself answers a dry-run: it reads the export and
// writes no database.
func TestFlowMigrateDryRunWritesNothing(t *testing.T) {
	l := setup(t)
	home := t.TempDir()
	source := filepath.Join(t.TempDir(), "export.json")
	export := `[{"uuid":"8e1d2c4a-0000-4000-8000-000000000001","description":"Ship it",` +
		`"status":"pending","entry":"20261021T120000Z","project":"demo"}]`
	if err := os.WriteFile(source, []byte(export), 0o644); err != nil {
		t.Fatal(err)
	}

	code, stdout, stderr := run(t, "--home", home, "--project", "sandbox_x",
		"flow", "migrate", "taskwarrior", "--source", source)
	if code != 0 {
		t.Fatalf("exit %d, stdout %q, stderr %q", code, stdout, stderr)
	}
	if !strings.Contains(stdout, "dry-run") {
		t.Errorf("stdout %q, want the dry-run report", stdout)
	}
	for _, dir := range []string{filepath.Join(home, "flow"), filepath.Join(l.home, ".jacazul")} {
		if _, err := os.Stat(dir); !os.IsNotExist(err) {
			t.Errorf("dry-run created %s: %v", dir, err)
		}
	}
}

// Without flags the engine gets what the launcher resolves: the canonical
// project, the global session and the default home, never an empty value
// the engine would fill in on its own.
func TestFlowEngineEnvUsesTheLauncherDefaults(t *testing.T) {
	l := setup(t)
	calls := fakeEngine(t, 0)
	t.Setenv("JACAZUL_FLOW_DATABASE_PATH", filepath.Join(l.home, "other.sqlite3"))

	if code, _, stderr := run(t, "flow", "migrate", "taskwarrior"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	id := filepath.Base(filepath.Dir(l.project)) + "_" + filepath.Base(l.project)
	want := flow.Env{
		ProjectID:    id,
		SessionID:    "global",
		Home:         filepath.Join(l.home, ".jacazul"),
		DatabasePath: filepath.Join(l.home, "other.sqlite3"),
	}
	if got := (*calls)[0].env; got != want {
		t.Errorf("env %+v, want %+v", got, want)
	}
}
