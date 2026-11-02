package cli

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/jacazul-ai/flow"
)

// opening is one project being opened: its Taskwarrior silo, its flow
// database, the engine commands the launcher runs and the migrations it
// asks for.
type opening struct {
	id         string
	home       string // the flow home, ~/.jacazul
	silo       string
	database   string
	calls      *[][]string
	migrations *[]flow.MigrateOptions
	exports    *[]string // the export each migration read
}

// openProject sets up a project with a fake engine that records the
// commands it is given. Migrations go to the pinned engine, recorded with
// the export they read, unless fail is set: then a migration writes
// nothing and returns fail.
func openProject(t *testing.T, fail error) opening {
	t.Helper()
	l := setup(t)
	id := filepath.Base(filepath.Dir(l.project)) + "_" + filepath.Base(l.project)
	o := opening{
		id:         id,
		home:       filepath.Join(l.home, ".jacazul"),
		silo:       filepath.Join(l.home, ".jacazul-ai", ".task", id),
		database:   filepath.Join(l.home, ".jacazul", "projects", id, "flow.sqlite3"),
		calls:      &[][]string{},
		migrations: &[]flow.MigrateOptions{},
		exports:    &[]string{},
	}
	saved := runEngine
	runEngine = func(_ context.Context, args []string, env flow.Env, _ flow.Streams) int {
		*o.calls = append(*o.calls, args)
		if env.DatabasePath != o.database {
			t.Errorf("engine database %q, want %q", env.DatabasePath, o.database)
		}
		return 0
	}
	t.Cleanup(func() { runEngine = saved })
	savedMigrate := migrateEngine
	migrateEngine = func(ctx context.Context, env flow.Env, options flow.MigrateOptions) (flow.MigrateResult, error) {
		*o.migrations = append(*o.migrations, options)
		if env.DatabasePath != o.database {
			t.Errorf("migration database %q, want %q", env.DatabasePath, o.database)
		}
		data, err := os.ReadFile(options.Source)
		if err != nil {
			t.Fatalf("export unreadable during the migration: %v", err)
		}
		*o.exports = append(*o.exports, string(data))
		if fail != nil {
			return flow.MigrateResult{}, fail
		}
		return flow.MigrateTaskwarrior(ctx, env, options)
	}
	t.Cleanup(func() { migrateEngine = savedMigrate })
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

// withDatabase creates the project database with the pinned engine. A
// non-empty origin makes it the database a migration from origin wrote.
func (o opening) withDatabase(t *testing.T, origin string) {
	t.Helper()
	env := flow.Env{ProjectID: o.id, Home: o.home, DatabasePath: o.database}
	if origin == "" {
		if _, err := flow.Init(context.Background(), env); err != nil {
			t.Fatal(err)
		}
		return
	}
	export := filepath.Join(t.TempDir(), "export.json")
	task := `[{"uuid":"8e1d2c4a-0000-4000-8000-000000000001","description":"Ship it","status":"pending","entry":"20261101T000000Z"}]`
	if err := os.WriteFile(export, []byte(task), 0o600); err != nil {
		t.Fatal(err)
	}
	options := flow.MigrateOptions{Source: export, Origin: origin, Apply: true}
	if _, err := flow.MigrateTaskwarrior(context.Background(), env, options); err != nil {
		t.Fatal(err)
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
	o := openProject(t, nil)
	o.withSilo(t)
	record := fakeTask(t, "")
	o.withDatabase(t, canonical(o.silo))

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
	o := openProject(t, nil)
	o.withSilo(t)
	t.Setenv("TASKRC", filepath.Join(t.TempDir(), "operator.taskrc"))
	record := fakeTask(t, `
grep -q '^uda.backlog.type=numeric' "$TASKRC" || { echo "TASKRC $TASKRC lacks the Jacazul UDAs" >&2; exit 3; }
for a in "$@"; do
  case "$a" in rc.data.location=*) dir=${a#rc.data.location=} ;; esac
done
echo touched > "$dir/taskchampion.sqlite3"
echo gc > "$dir/completed.data"
echo '[{"uuid":"8e1d2c4a-0000-4000-8000-000000000001","description":"Ship it","status":"pending","entry":"20261101T000000Z"}]'
`)

	code, stdout, stderr := run(t, "flow", "status")
	if code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	o.siloUntouched(t)
	if stdout != "" {
		t.Errorf("stdout %q, want the migration report on stderr", stdout)
	}
	if !strings.Contains(stderr, "migrated "+o.silo) || !strings.Contains(stderr, "(created ") {
		t.Errorf("stderr %q lacks the migration summary", stderr)
	}

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

	// A dry-run, then the apply, both on the copy, with the silo's
	// canonical path as the origin.
	migrations := *o.migrations
	if len(migrations) != 2 || migrations[0].Apply || !migrations[1].Apply {
		t.Fatalf("migrations %+v, want a dry-run then an apply", migrations)
	}
	for _, m := range migrations {
		if m.Origin != canonical(o.silo) {
			t.Errorf("origin %q, want %q", m.Origin, canonical(o.silo))
		}
		if m.LegacyDataDir != copied {
			t.Errorf("sessions read from %q, want the copy %s", m.LegacyDataDir, copied)
		}
	}
	if !strings.Contains((*o.exports)[1], "Ship it") {
		t.Errorf("migration read %q, want the task export", (*o.exports)[1])
	}
	if want := [][]string{{"status"}}; !slices.EqualFunc(*o.calls, want, slices.Equal) {
		t.Errorf("engine calls %q, want %q", *o.calls, want)
	}

	// The database came from this silo: the next run neither migrates nor
	// warns.
	if code, stdout, stderr := run(t, "flow", "status"); code != 0 || stdout != "" || stderr != "" {
		t.Errorf("second run: exit %d, stdout %q, stderr %q, want a silent run", code, stdout, stderr)
	}
	if len(*o.migrations) != 2 {
		t.Errorf("the second run migrated again: %+v", *o.migrations)
	}
}

// ERROR issues never stop the migration: the apply runs, every issue is
// printed with the task it names, and an ACTION: sends the agent to them.
func TestOpeningMigratesDespiteRecordErrors(t *testing.T) {
	o := openProject(t, nil)
	o.withSilo(t)
	fakeTask(t, `echo '[{"uuid":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","description":"Late","status":"pending","entry":"20261101T000000Z","due":"not-a-date"}]'`)

	code, _, stderr := run(t, "flow", "status")
	if code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	for _, want := range []string{"ERROR", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "ACTION:"} {
		if !strings.Contains(stderr, want) {
			t.Errorf("stderr lacks %q:\n%s", want, stderr)
		}
	}
	if !exists(o.database) {
		t.Error("no database after a migration with ERROR issues")
	}
	if want := [][]string{{"status"}}; !slices.EqualFunc(*o.calls, want, slices.Equal) {
		t.Errorf("engine calls %q, want %q", *o.calls, want)
	}
	o.siloUntouched(t)
}

// Opening creates the database itself and says so, so a new database never
// appears without a word; the command's own output stays on stdout.
func TestOpeningWithoutDataCreatesTheDatabase(t *testing.T) {
	o := openProject(t, nil)
	noTask(t)

	code, stdout, stderr := run(t, "flow", "status")
	if code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if want := [][]string{{"status"}}; !slices.EqualFunc(*o.calls, want, slices.Equal) {
		t.Errorf("engine calls %q, want %q", *o.calls, want)
	}
	if !exists(o.database) {
		t.Fatal("no database after opening")
	}
	if want := "created the project database at " + o.database; !strings.Contains(stderr, want) {
		t.Errorf("stderr %q lacks %q", stderr, want)
	}
	if stdout != "" {
		t.Errorf("stdout %q, want it left to the command", stdout)
	}
}

func TestOpeningACurrentDatabaseIsSilent(t *testing.T) {
	o := openProject(t, nil)
	o.withDatabase(t, "")

	code, stdout, stderr := run(t, "flow", "status")
	if code != 0 || stdout != "" || stderr != "" {
		t.Fatalf("exit %d, stdout %q, stderr %q, want a silent run", code, stdout, stderr)
	}
}

// While the silo stays in place next to a database that did not come from
// migrating it, every run warns; only a migration from that silo, or the
// silo moving out, ends it. The warning never stops the command.
func TestOpeningWarnsWhileTheSiloOutlivesAForeignDatabase(t *testing.T) {
	for name, origin := range map[string]func(o opening) string{
		"no migration": func(opening) string { return "" },
		"another silo": func(o opening) string { return canonical(filepath.Join(filepath.Dir(o.silo), "other")) },
	} {
		t.Run(name, func(t *testing.T) {
			o := openProject(t, nil)
			o.withSilo(t)
			o.withDatabase(t, origin(o))
			record := fakeTask(t, "")

			for range 2 {
				code, _, stderr := run(t, "flow", "status")
				if code != 0 {
					t.Fatalf("exit %d, stderr %q", code, stderr)
				}
				if !strings.Contains(stderr, o.silo) || !strings.Contains(stderr, "ACTION:") {
					t.Errorf("stderr %q, want a warning naming the silo with an ACTION:", stderr)
				}
			}
			if want := [][]string{{"status"}, {"status"}}; !slices.EqualFunc(*o.calls, want, slices.Equal) {
				t.Errorf("engine calls %q, want %q", *o.calls, want)
			}
			if _, err := os.Stat(record); !os.IsNotExist(err) {
				t.Error("task ran although the database exists")
			}
			o.siloUntouched(t)
		})
	}
}

// A database migrated from this very silo is the right one: no warning,
// even when the launcher reaches the silo through a symbolic link.
func TestOpeningADatabaseMigratedFromTheSiloIsSilent(t *testing.T) {
	o := openProject(t, nil)
	o.withSilo(t)
	o.withDatabase(t, canonical(o.silo))
	link := filepath.Join(t.TempDir(), "home")
	if err := os.Symlink(filepath.Dir(filepath.Dir(o.silo)), link); err != nil {
		t.Fatal(err)
	}

	for _, args := range [][]string{{"flow", "status"}, {"--home", link, "flow", "status"}} {
		if code, stdout, stderr := run(t, args...); code != 0 || stdout != "" || stderr != "" {
			t.Errorf("%q: exit %d, stdout %q, stderr %q, want a silent run", args, code, stdout, stderr)
		}
	}
}

// jacazul flow init is opening the project: it creates the database and
// says so, and the engine is not asked to do it again.
func TestFlowInitIsOpeningTheProject(t *testing.T) {
	o := openProject(t, nil)

	code, _, stderr := run(t, "flow", "init")
	if code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if len(*o.calls) != 0 {
		t.Errorf("engine calls %q, want none", *o.calls)
	}
	if !exists(o.database) || !strings.Contains(stderr, "created the project database") {
		t.Errorf("database %s not created and reported: stderr %q", o.database, stderr)
	}

	if code, stdout, stderr := run(t, "flow", "init"); code != 0 || stdout != "" || stderr != "" {
		t.Errorf("second init: exit %d, stdout %q, stderr %q, want a silent run", code, stdout, stderr)
	}
}

// Without task and without a terminal there is nobody to ask, so the
// launcher stops instead of choosing for the operator.
func TestOpeningWithoutTaskOrTerminalStops(t *testing.T) {
	o := openProject(t, nil)
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
			o := openProject(t, nil)
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
			// Proceeding is a fresh database, created and reported by
			// opening; installing creates nothing.
			if exists(o.database) != (tc.code == 0) {
				t.Errorf("database exists %v after %q", exists(o.database), tc.answer)
			}
			if tc.code == 0 && !strings.Contains(stderr, "created the project database") {
				t.Errorf("stderr %q does not report the new database", stderr)
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
			o := openProject(t, nil)
			o.withSilo(t)
			fakeTask(t, script)

			code, _, stderr := run(t, "flow", "status")
			if code != 1 || !strings.Contains(stderr, "ACTION:") {
				t.Fatalf("exit %d, stderr %q", code, stderr)
			}
			if name == "task fails" && !strings.Contains(stderr, "database is locked") {
				t.Errorf("stderr %q hides task's own message", stderr)
			}
			if len(*o.calls) != 0 || len(*o.migrations) != 0 {
				t.Errorf("engine ran: %q, migrations %+v", *o.calls, *o.migrations)
			}
			o.siloUntouched(t)
		})
	}
}

// --dry shows where the storage is and what opening would do, runs the
// migration as a dry-run, and runs no command: nothing is written.
func TestOpeningDryRunWritesNothing(t *testing.T) {
	for name, flag := range map[string][]string{"flag": {"--dry"}, "environment": nil} {
		t.Run(name, func(t *testing.T) {
			o := openProject(t, nil)
			o.withSilo(t)
			record := fakeTask(t, `echo '[]'`)
			if flag == nil {
				t.Setenv("DRY", "true")
			}

			code, stdout, stderr := run(t, append(flag, "flow", "status")...)
			if code != 0 {
				t.Fatalf("exit %d, stderr %q", code, stderr)
			}
			for _, want := range []string{o.database, o.silo, "migrate", filepath.Dir(record), "would migrate"} {
				if !strings.Contains(stdout, want) {
					t.Errorf("dry output lacks %q:\n%s", want, stdout)
				}
			}
			if len(*o.calls) != 0 {
				t.Errorf("engine ran %q in a dry run", *o.calls)
			}
			if m := *o.migrations; len(m) != 1 || m[0].Apply {
				t.Fatalf("migrations %+v, want one dry-run", m)
			}
			if dataDir(t, record) == o.silo {
				t.Error("dry-run exported the silo itself, not a copy")
			}
			if _, err := os.Stat(o.database); !os.IsNotExist(err) {
				t.Errorf("dry-run created the database: %v", err)
			}
			o.siloUntouched(t)
		})
	}
}

func TestOpeningDryRunWithADatabaseRunsNothing(t *testing.T) {
	o := openProject(t, nil)
	if err := os.MkdirAll(filepath.Dir(o.database), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(o.database, nil, 0o644); err != nil {
		t.Fatal(err)
	}

	code, stdout, _ := run(t, "--dry", "flow", "status")
	if code != 0 || !strings.Contains(stdout, o.database) {
		t.Fatalf("exit %d, stdout %q", code, stdout)
	}
	if len(*o.calls) != 0 {
		t.Errorf("engine ran in a dry run: %q", *o.calls)
	}
}

// An explicit migration without --source is the automatic one: the same
// copy, the same library call, so its database carries the origin too.
// --apply writes; anything else is a dry-run, the engine's default.
func TestExplicitMigrationGoesThroughTheLibrary(t *testing.T) {
	for _, tc := range []struct {
		args  []string
		apply bool
	}{
		{[]string{"--dry-run"}, false},
		{nil, false},
		{[]string{"--apply"}, true},
	} {
		t.Run(strings.Join(tc.args, " "), func(t *testing.T) {
			o := openProject(t, nil)
			o.withSilo(t)
			record := fakeTask(t, `echo '[]'`)

			code, _, stderr := run(t, append([]string{"flow", "migrate", "taskwarrior"}, tc.args...)...)
			if code != 0 {
				t.Fatalf("exit %d, stderr %q", code, stderr)
			}
			if len(*o.calls) != 0 {
				t.Errorf("engine command ran: %q", *o.calls)
			}
			m := *o.migrations
			if len(m) == 0 || m[len(m)-1].Apply != tc.apply || m[0].Origin != canonical(o.silo) {
				t.Errorf("migrations %+v, want apply %v from %s", m, tc.apply, canonical(o.silo))
			}
			if exists(o.database) != tc.apply {
				t.Errorf("database exists %v, want %v", exists(o.database), tc.apply)
			}
			if dataDir(t, record) == o.silo {
				t.Error("explicit migration exported the silo itself")
			}
			o.siloUntouched(t)
		})
	}
}

// The library has no room for the engine's other migration options, so an
// explicit migration that asks for one is refused and pointed at --source,
// the engine's own path.
func TestExplicitMigrationRefusesOtherOptions(t *testing.T) {
	o := openProject(t, nil)
	o.withSilo(t)
	record := fakeTask(t, `echo '[]'`)

	code, _, stderr := run(t, "flow", "migrate", "taskwarrior", "--legacy-map", "map.json")
	if code != 1 || !strings.Contains(stderr, "--legacy-map") || !strings.Contains(stderr, "ACTION:") {
		t.Fatalf("exit %d, stderr %q, want a refusal with an ACTION:", code, stderr)
	}
	if len(*o.migrations) != 0 || len(*o.calls) != 0 {
		t.Errorf("migrations %+v, engine calls %q, want none", *o.migrations, *o.calls)
	}
	if _, err := os.Stat(record); !os.IsNotExist(err) {
		t.Error("task ran for a refused migration")
	}
}

// --dry wins over an explicit --apply, and a bare jacazul flow does not
// crash.
func TestDryRunNeverApplies(t *testing.T) {
	o := openProject(t, nil)
	o.withSilo(t)
	fakeTask(t, `echo '[]'`)

	if code, _, stderr := run(t, "--dry", "flow", "migrate", "taskwarrior", "--apply"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	for _, m := range *o.migrations {
		if m.Apply {
			t.Errorf("dry run applied: %+v", m)
		}
	}
	if _, err := os.Stat(o.database); !os.IsNotExist(err) {
		t.Errorf("dry run created the database: %v", err)
	}
	run(t, "flow")
}

// Commands that open no storage do not trigger a migration.
func TestOpeningSkipsCommandsWithoutStorage(t *testing.T) {
	for _, command := range []string{"info", "help", "--help", "--version"} {
		t.Run(command, func(t *testing.T) {
			o := openProject(t, nil)
			o.withSilo(t)
			record := fakeTask(t, `echo '[]'`)

			run(t, "flow", command)
			if want := [][]string{{command}}; !slices.EqualFunc(*o.calls, want, slices.Equal) {
				t.Errorf("engine calls %q, want %q", *o.calls, want)
			}
			if _, err := os.Stat(record); !os.IsNotExist(err) {
				t.Error("task ran for a command that opens no storage")
			}
		})
	}
}

// A failed migration stops with the engine's own guidance and leaves no
// database behind, so the next run can try again: the library refuses to
// migrate onto an existing one.
func TestOpeningFailedMigrationLeavesNoDatabase(t *testing.T) {
	o := openProject(t, errors.New("read export: disk on fire\nACTION: Fix the disk."))
	o.withSilo(t)
	fakeTask(t, "echo '[]'")

	code, _, stderr := run(t, "flow", "status")
	if code != 1 || !strings.Contains(stderr, "disk on fire\nACTION: Fix the disk.") {
		t.Errorf("exit %d, stderr %q, want 1 and the engine's guidance", code, stderr)
	}
	if len(*o.calls) != 0 {
		t.Errorf("engine calls %q, want none", *o.calls)
	}
	if _, err := os.Stat(o.database); !os.IsNotExist(err) {
		t.Errorf("failed migration left %s: %v", o.database, err)
	}
	o.siloUntouched(t)
}

// The engine flags that take a value would make the engine open another
// database than the one opening settled, so jacazul refuses them, in both
// spellings and wherever they sit before "--", and names what to use.
func TestFlowRefusesEngineValueFlags(t *testing.T) {
	for _, flag := range []string{"--project", "--session", "--home", "--database-path", "--taskdata", "--task-binary"} {
		for _, args := range [][]string{
			{"flow", flag, "x", "status"},
			{"flow", flag + "=x", "status"},
			{"flow", "-v", "status", flag, "x"},
		} {
			t.Run(strings.Join(args, " "), func(t *testing.T) {
				o := openProject(t, nil)
				o.withSilo(t)
				record := fakeTask(t, `echo '[]'`)

				code, _, stderr := run(t, args...)
				if code != 1 || !strings.Contains(stderr, flag) || !strings.Contains(stderr, "ACTION:") {
					t.Fatalf("exit %d, stderr %q, want a refusal of %s with an ACTION:", code, stderr, flag)
				}
				if len(*o.calls) != 0 {
					t.Errorf("engine ran: %q", *o.calls)
				}
				if _, err := os.Stat(record); !os.IsNotExist(err) {
					t.Error("task ran for a refused command")
				}
				if exists(o.database) {
					t.Error("database created for a refused command")
				}
				o.siloUntouched(t)
			})
		}
	}
}

// After "--" the arguments belong to the command, not to the engine.
func TestFlowPassesValueFlagsAfterTheSeparator(t *testing.T) {
	o := openProject(t, nil)

	if code, _, stderr := run(t, "flow", "note", "--", "--project", "x"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if want := [][]string{{"note", "--", "--project", "x"}}; !slices.EqualFunc(*o.calls, want, slices.Equal) {
		t.Errorf("engine calls %q, want %q", *o.calls, want)
	}
}

// The command is the first argument that is not a flag, so a leading
// engine flag neither hides a command that opens storage nor turns one
// that does not into a migration.
func TestFlowFindsTheCommandPastLeadingFlags(t *testing.T) {
	for _, tc := range []struct {
		args  []string
		opens bool
	}{
		{[]string{"-v", "info"}, false},
		{[]string{"--verbose", "help"}, false},
		{[]string{"-V"}, false},
		{[]string{"-v", "--help"}, false},
		{[]string{"-v", "status"}, true},
		{[]string{"--verbose", "init"}, true},
	} {
		t.Run(strings.Join(tc.args, " "), func(t *testing.T) {
			o := openProject(t, nil)
			noTask(t)

			code, _, stderr := run(t, append([]string{"flow"}, tc.args...)...)
			if code != 0 {
				t.Fatalf("exit %d, stderr %q", code, stderr)
			}
			if exists(o.database) != tc.opens {
				t.Errorf("database exists %v, want %v", exists(o.database), tc.opens)
			}
		})
	}
}

// Every engine global option that takes a value must be one jacazul
// refuses; a new one in the pinned engine fails here until it is added.
func TestRefusedFlagsCoverTheEngineHelp(t *testing.T) {
	var stdout strings.Builder
	flow.Run(context.Background(), []string{"--help"}, flow.Env{}, flow.Streams{Stdout: &stdout, Stderr: &stdout})
	_, options, ok := strings.Cut(stdout.String(), "GLOBAL OPTIONS")
	if !ok {
		t.Fatalf("engine help has no GLOBAL OPTIONS:\n%s", stdout.String())
	}
	found := 0
	for _, field := range strings.Fields(options) {
		name, _, takesValue := strings.Cut(field, "=")
		if !takesValue || !strings.HasPrefix(name, "--") {
			continue
		}
		found++
		if _, ok := engineValueFlags[name]; !ok {
			t.Errorf("engine global option %s takes a value but jacazul does not refuse it", name)
		}
	}
	if found == 0 {
		t.Fatalf("no value-taking option read from the engine help:\n%s", options)
	}
}

// --verbose shows what opening found and decided on a real run, on stderr
// so the command's output stays clean, and makes the engine verbose too.
func TestVerboseShowsTheOpeningDecision(t *testing.T) {
	o := openProject(t, nil)
	o.withDatabase(t, "")

	code, stdout, stderr := run(t, "--verbose", "flow", "status")
	if code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	for _, want := range []string{o.database, o.silo, "use the flow database", "is current"} {
		if !strings.Contains(stderr, want) {
			t.Errorf("stderr lacks %q:\n%s", want, stderr)
		}
	}
	if stdout != "" {
		t.Errorf("stdout %q, want it left to the command", stdout)
	}
	if want := [][]string{{"-v", "status"}}; !slices.EqualFunc(*o.calls, want, slices.Equal) {
		t.Errorf("engine calls %q, want %q", *o.calls, want)
	}
}
