package cli

import (
	"context"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/jacazul-ai/flow"
)

// opening is one project being opened: its Taskwarrior silo, its flow
// database and the engine calls the launcher makes.
type opening struct {
	silo     string
	database string
	calls    *[][]string
	exports  *[]string // the export each migration read
}

// openProject sets up a project with a fake engine that records its
// arguments and, for a migration, the export it was given. migrateCode is
// what the migration returns; every other call returns 0.
func openProject(t *testing.T, migrateCode int) opening {
	t.Helper()
	l := setup(t)
	id := filepath.Base(filepath.Dir(l.project)) + "_" + filepath.Base(l.project)
	o := opening{
		silo:     filepath.Join(l.home, ".jacazul-ai", ".task", id),
		database: filepath.Join(l.home, ".jacazul", "projects", id, "flow.sqlite3"),
		calls:    &[][]string{},
		exports:  &[]string{},
	}
	saved := runEngine
	runEngine = func(_ context.Context, args []string, env flow.Env, _ flow.Streams) int {
		*o.calls = append(*o.calls, args)
		if env.DatabasePath != o.database {
			t.Errorf("engine database %q, want %q", env.DatabasePath, o.database)
		}
		if len(args) > 0 && args[0] == "migrate" {
			i := slices.Index(args, "--source")
			if i < 0 || i+1 >= len(args) {
				t.Fatalf("migration without --source: %q", args)
			}
			data, err := os.ReadFile(args[i+1])
			if err != nil {
				t.Fatalf("export unreadable during the migration: %v", err)
			}
			*o.exports = append(*o.exports, string(data))
			// The engine creates the database before it can fail.
			if err := os.MkdirAll(filepath.Dir(o.database), 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(o.database, nil, 0o644); err != nil {
				t.Fatal(err)
			}
			return migrateCode
		}
		return 0
	}
	t.Cleanup(func() { runEngine = saved })
	interactive = func() bool { return false }
	t.Cleanup(func() { interactive = func() bool { return isTerminal(os.Stdin) } })
	return o
}

// withSilo writes a Taskwarrior database and a session lane into the silo.
func (o opening) withSilo(t *testing.T) {
	t.Helper()
	if err := os.MkdirAll(o.silo, 0o755); err != nil {
		t.Fatal(err)
	}
	for name, content := range map[string]string{
		"taskchampion.sqlite3": "original",
		"focus-aaaaaaaa.json":  `{"focused_plan": "demo"}`,
	} {
		if err := os.WriteFile(filepath.Join(o.silo, name), []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
}

// fakeTask installs a task binary from script and returns a file where the
// script records its arguments, one per line.
func fakeTask(t *testing.T, script string) string {
	t.Helper()
	dir := t.TempDir()
	record := filepath.Join(dir, "args")
	bin := filepath.Join(dir, "task")
	body := "#!/bin/sh\nfor a in \"$@\"; do echo \"$a\"; done > " + record + "\n" + script
	if err := os.WriteFile(bin, []byte(body), 0o755); err != nil {
		t.Fatal(err)
	}
	saved := findTask
	findTask = func(string) string { return bin }
	t.Cleanup(func() { findTask = saved })
	return record
}

func noTask(t *testing.T) {
	t.Helper()
	saved := findTask
	findTask = func(string) string { return "" }
	t.Cleanup(func() { findTask = saved })
}

// dataDir is the rc.data.location the fake task received.
func dataDir(t *testing.T, record string) string {
	t.Helper()
	data, err := os.ReadFile(record)
	if err != nil {
		t.Fatalf("task never ran: %v", err)
	}
	for _, arg := range strings.Split(string(data), "\n") {
		if dir, ok := strings.CutPrefix(arg, "rc.data.location="); ok {
			return dir
		}
	}
	t.Fatalf("task ran without rc.data.location:\n%s", data)
	return ""
}

func (o opening) siloUntouched(t *testing.T) {
	t.Helper()
	entries, err := os.ReadDir(o.silo)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 2 {
		t.Errorf("silo has %d entries, want the 2 it started with", len(entries))
	}
	data, err := os.ReadFile(filepath.Join(o.silo, "taskchampion.sqlite3"))
	if err != nil || string(data) != "original" {
		t.Errorf("silo database changed: %q, %v", data, err)
	}
}

func TestOpeningUsesAnExistingDatabase(t *testing.T) {
	o := openProject(t, 0)
	o.withSilo(t)
	record := fakeTask(t, "")
	if err := os.MkdirAll(filepath.Dir(o.database), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(o.database, nil, 0o644); err != nil {
		t.Fatal(err)
	}

	if code, _, stderr := run(t, "flow", "status"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if want := [][]string{{"status"}}; !slices.EqualFunc(*o.calls, want, slices.Equal) {
		t.Errorf("engine calls %q, want %q", *o.calls, want)
	}
	if _, err := os.Stat(record); !os.IsNotExist(err) {
		t.Error("task ran although the database exists")
	}
}

// The migration reads a copy of the silo: the fake task writes into the
// directory it is given, and the silo must come out as it went in. The
// export uses the Jacazul taskrc whatever the operator's own says, so the
// UDAs keep their types.
func TestOpeningMigratesACopyOfTheSilo(t *testing.T) {
	o := openProject(t, 0)
	o.withSilo(t)
	t.Setenv("TASKRC", filepath.Join(t.TempDir(), "operator.taskrc"))
	record := fakeTask(t, `
grep -q '^uda.backlog.type=numeric' "$TASKRC" || { echo "TASKRC $TASKRC lacks the Jacazul UDAs" >&2; exit 3; }
for a in "$@"; do
  case "$a" in rc.data.location=*) dir=${a#rc.data.location=} ;; esac
done
echo touched > "$dir/taskchampion.sqlite3"
echo gc > "$dir/completed.data"
echo '[{"uuid":"8e1d2c4a-0000-4000-8000-000000000001","description":"Ship it"}]'
`)

	if code, _, stderr := run(t, "flow", "status"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	o.siloUntouched(t)

	copied := dataDir(t, record)
	if copied == o.silo {
		t.Fatal("task read the silo itself, not a copy")
	}
	if _, err := os.Stat(copied); !os.IsNotExist(err) {
		t.Errorf("copy %s left behind: %v", copied, err)
	}
	args, _ := os.ReadFile(record)
	for _, flag := range []string{"rc.gc=off", "rc.recurrence=off", "rc.hooks=off", "export"} {
		if !slices.Contains(strings.Split(string(args), "\n"), flag) {
			t.Errorf("task args lack %s:\n%s", flag, args)
		}
	}

	calls := *o.calls
	if len(calls) != 2 {
		t.Fatalf("engine calls %q, want the migration then status", calls)
	}
	migrate := calls[0]
	if !slices.Equal(migrate[:2], []string{"migrate", "taskwarrior"}) || !slices.Contains(migrate, "--apply") {
		t.Errorf("migration call %q", migrate)
	}
	if i := slices.Index(migrate, "--legacy-data-dir"); i < 0 || migrate[i+1] != copied {
		t.Errorf("migration %q does not read the sessions from the copy %s", migrate, copied)
	}
	if !strings.Contains((*o.exports)[0], "Ship it") {
		t.Errorf("migration read %q, want the task export", (*o.exports)[0])
	}
	if !slices.Equal(calls[1], []string{"status"}) {
		t.Errorf("after the migration the engine ran %q, want status", calls[1])
	}
}

func TestOpeningWithoutDataCreatesTheDatabase(t *testing.T) {
	o := openProject(t, 0)
	noTask(t)

	if code, _, stderr := run(t, "flow", "status"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if want := [][]string{{"status"}}; !slices.EqualFunc(*o.calls, want, slices.Equal) {
		t.Errorf("engine calls %q, want %q", *o.calls, want)
	}
}

// Without task and without a terminal there is nobody to ask, so the
// launcher stops instead of choosing for the operator.
func TestOpeningWithoutTaskOrTerminalStops(t *testing.T) {
	o := openProject(t, 0)
	o.withSilo(t)
	noTask(t)

	code, _, stderr := run(t, "flow", "status")
	if code != 1 || !strings.Contains(stderr, "ACTION:") {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if len(*o.calls) != 0 {
		t.Errorf("engine ran: %q", *o.calls)
	}
	if _, err := os.Stat(o.database); !os.IsNotExist(err) {
		t.Errorf("database created: %v", err)
	}
	o.siloUntouched(t)
}

func TestOpeningWithoutTaskAsksTheOperator(t *testing.T) {
	for name, tc := range map[string]struct {
		answer string
		code   int
		calls  [][]string
		output string
	}{
		"proceed": {answer: "p\n", code: 0, calls: [][]string{{"status"}}},
		"install": {answer: "i\n", code: 1, output: "install"},
	} {
		t.Run(name, func(t *testing.T) {
			o := openProject(t, 0)
			o.withSilo(t)
			noTask(t)
			interactive = func() bool { return true }
			saved := input
			input = strings.NewReader(tc.answer)
			t.Cleanup(func() { input = saved })

			code, stdout, stderr := run(t, "flow", "status")
			if code != tc.code {
				t.Fatalf("exit %d, want %d; stderr %q", code, tc.code, stderr)
			}
			if !strings.Contains(stdout+stderr, "Taskwarrior") {
				t.Errorf("prompt does not name Taskwarrior: %q", stdout+stderr)
			}
			if !strings.Contains(strings.ToLower(stdout+stderr), tc.output) {
				t.Errorf("output %q lacks %q", stdout+stderr, tc.output)
			}
			if !slices.EqualFunc(*o.calls, tc.calls, slices.Equal) {
				t.Errorf("engine calls %q, want %q", *o.calls, tc.calls)
			}
			o.siloUntouched(t)
		})
	}
}

func TestOpeningStopsWhenTheExportFails(t *testing.T) {
	for name, script := range map[string]string{
		"task fails":   "echo 'database is locked' >&2; exit 2",
		"invalid json": "echo 'not json'",
	} {
		t.Run(name, func(t *testing.T) {
			o := openProject(t, 0)
			o.withSilo(t)
			fakeTask(t, script)

			code, _, stderr := run(t, "flow", "status")
			if code != 1 || !strings.Contains(stderr, "ACTION:") {
				t.Fatalf("exit %d, stderr %q", code, stderr)
			}
			if name == "task fails" && !strings.Contains(stderr, "database is locked") {
				t.Errorf("stderr %q hides task's own message", stderr)
			}
			if len(*o.calls) != 0 {
				t.Errorf("engine ran: %q", *o.calls)
			}
			o.siloUntouched(t)
		})
	}
}

// A failed migration leaves no database behind, so the next run can try
// again: the engine refuses to migrate onto an existing one.
func TestOpeningFailedMigrationLeavesNoDatabase(t *testing.T) {
	o := openProject(t, 4)
	o.withSilo(t)
	fakeTask(t, "echo '[]'")

	code, _, _ := run(t, "flow", "status")
	if code != 4 {
		t.Errorf("exit %d, want the migration's 4", code)
	}
	if len(*o.calls) != 1 {
		t.Errorf("engine calls %q, want only the migration", *o.calls)
	}
	if _, err := os.Stat(o.database); !os.IsNotExist(err) {
		t.Errorf("failed migration left %s: %v", o.database, err)
	}
	o.siloUntouched(t)
}
