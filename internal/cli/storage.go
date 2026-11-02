package cli

import (
	"bufio"
	"bytes"
	"cmp"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
	"strings"

	"github.com/jacazul-ai/flow"

	"github.com/jacazul-ai/launcher/internal/bootstrap/environment"
	tasktmpl "github.com/jacazul-ai/launcher/templates/taskwarrior"
)

var dataLocation = regexp.MustCompile(`(?m)^data\.location=.*$`)

// interactive reports whether the operator can answer a question; tests
// replace it.
var interactive = func() bool { return isTerminal(os.Stdin) }

// input is where the operator's answer comes from; tests replace it.
var input io.Reader = os.Stdin

// findTask locates the real Taskwarrior binary, never the Jacazul guard in
// root/scripts; tests replace it.
var findTask = func(root string) string {
	if task := os.Getenv("JACAZUL_REAL_TASK"); task != "" && isExecutable(task) {
		return task
	}
	return environment.Resolve(environment.Input{
		Getenv:   os.Getenv,
		SkipDirs: []string{filepath.Join(root, "scripts")},
	}).RealTask
}

// command is the engine command in args and its index: the first argument
// that is not a flag, before any "--". With the engine's value flags
// refused, every flag before it stands alone. It is "", -1 for none.
func command(args []string) (string, int) {
	for i, arg := range args {
		if arg == "--" {
			break
		}
		if !strings.HasPrefix(arg, "-") {
			return arg, i
		}
	}
	return "", -1
}

// opensStorage reports whether the engine command opens the project's
// storage; help, version and info do not, so they trigger no migration.
func opensStorage(args []string) bool {
	name, i := command(args)
	if i < 0 || slices.Contains([]string{"info", "help"}, name) {
		return false
	}
	return !slices.ContainsFunc(args[:i], func(arg string) bool {
		return slices.Contains([]string{"--help", "-h", "--version", "-V"}, arg)
	})
}

// openStorage settles the project's storage before an engine command, as
// "Opening a project" in docs/ARCHITECTURE.md lays out: an existing flow
// database is used, a Taskwarrior silo is migrated, and nothing at all
// means a new database. Using or creating a database goes through
// initDatabase. It returns non-zero when the command must not run. The
// silo is only ever read.
//
// A dry run prints the locations and the decision, runs the migration as
// a dry-run, and writes nothing. Verbose prints the same report on a real
// run, on stderr, and says when the database is current.
func openStorage(ctx context.Context, root, silo string, env flow.Env, streams flow.Streams, dry, verbose bool) int {
	found := exists(env.DatabasePath)
	data := hasTaskwarrior(silo)
	task := ""
	if !found && data {
		task = findTask(root)
	}
	action := "create a new flow database"
	switch {
	case found:
		action = "use the flow database"
	case data && task == "":
		action = "ask: install Taskwarrior, or proceed with a new flow database"
	case data:
		action = "migrate a copy of the silo"
	}
	if dry || verbose {
		w, header := streams.Stderr, "🐊 jacazul flow: opening the project"
		if dry {
			w, header = streams.Stdout, "🐊 jacazul flow (dry): nothing is written"
		}
		fmt.Fprintln(w, header)
		fmt.Fprintf(w, "   database  %s (%s)\n", env.DatabasePath, either(found, "exists", "missing"))
		fmt.Fprintf(w, "   silo      %s (%s)\n", silo, either(data, "Taskwarrior data", "no Taskwarrior data"))
		if !found && data {
			fmt.Fprintf(w, "   task      %s\n", cmp.Or(task, "not found"))
		}
		fmt.Fprintf(w, "   action    %s\n", action)
	}

	switch {
	case dry && (found || !data || task == ""):
		return 0
	case found || !data:
		return initDatabase(ctx, silo, data, env, streams, verbose)
	case task == "":
		if code := askWithoutTask(streams); code != 0 {
			return code
		}
		return initDatabase(ctx, silo, data, env, streams, verbose)
	case dry:
		return migrate(ctx, task, silo, env, streams.Stdout, streams.Stderr, false)
	}
	// The migration report goes to stderr, so the output of the command
	// that triggered it stays clean for whoever reads it.
	fmt.Fprintf(streams.Stderr, "🔄 jacazul flow: migrating %s into %s\n", silo, env.DatabasePath)
	return migrate(ctx, task, silo, env, streams.Stderr, streams.Stderr, true)
}

// initDatabase creates the project database or brings its schema up to
// date with flow.Init, and says which on stderr; a current database is
// opened in silence unless verbose. While a Taskwarrior silo still sits
// next to a database that did not come from migrating it, every run warns,
// so the operator moves the silo out once it is no longer needed. Init's
// errors carry their own ACTION: and are printed as they are.
func initDatabase(ctx context.Context, silo string, data bool, env flow.Env, streams flow.Streams, verbose bool) int {
	result, err := flow.Init(ctx, env)
	if err != nil {
		fmt.Fprintln(streams.Stderr, err)
		return 1
	}
	switch {
	case result.Created:
		fmt.Fprintf(streams.Stderr, "🐊 jacazul flow: created the project database at %s (schema v%d)\n", result.Path, result.To)
	case result.Upgraded:
		fmt.Fprintf(streams.Stderr, "🐊 jacazul flow: upgraded the project database at %s from schema v%d to v%d\n", result.Path, result.From, result.To)
	case verbose:
		fmt.Fprintf(streams.Stderr, "🐊 jacazul flow: the project database at %s is current (schema v%d)\n", result.Path, result.To)
	}
	if data && (result.Origin == nil || result.Origin.Path != canonical(silo)) {
		fmt.Fprintf(streams.Stderr, "⚠️  jacazul flow: the Taskwarrior data at %s is still in place, and %s did not come from migrating it\n", silo, result.Path)
		fmt.Fprintf(streams.Stderr, "ACTION: The flow database is the one in use. Once you no longer need the Taskwarrior data, move %s out of the way.\n", silo)
	}
	return 0
}

// explicitMigration reports whether args ask the engine to migrate
// Taskwarrior data that jacazul must export first: no --source snapshot,
// no --issues listing and no help.
func explicitMigration(args []string) bool {
	name, i := command(args)
	if name != "migrate" || i+1 >= len(args) || args[i+1] != "taskwarrior" {
		return false
	}
	for _, arg := range args[i+2:] {
		if slices.Contains([]string{"--issues", "--source", "--help", "-h"}, arg) || strings.HasPrefix(arg, "--source=") {
			return false
		}
	}
	return true
}

// migrationOptions reads an explicit migration's options: whether it
// applies, and the first option the library migration has no place for,
// or "" when there is none. Without --apply it is a dry-run, as for the
// engine.
func migrationOptions(args []string) (apply bool, other string) {
	_, i := command(args)
	for _, arg := range args[i+2:] {
		switch arg {
		case "--apply":
			apply = true
		case "--dry-run", "-v", "--verbose":
		default:
			return apply, arg
		}
	}
	return apply, ""
}

// hasTaskwarrior reports whether dir holds a Taskwarrior database: the
// taskchampion file of Taskwarrior 3 or the pending file of Taskwarrior 2.
// Session lanes alone are nothing to migrate.
func hasTaskwarrior(dir string) bool {
	return exists(filepath.Join(dir, "taskchampion.sqlite3")) || exists(filepath.Join(dir, "pending.data"))
}

// askWithoutTask asks whether to install Taskwarrior or start without the
// migration, and returns 0 only for the second. Without a terminal nobody
// can answer, so it stops instead of choosing.
func askWithoutTask(streams flow.Streams) int {
	if !interactive() {
		fmt.Fprintln(streams.Stderr, "❌ jacazul flow: this project has Taskwarrior data to migrate, but no task binary was found")
		fmt.Fprintln(streams.Stderr, "ACTION: Install Taskwarrior, or run jacazul flow in a terminal to choose to start without the migration.")
		return 1
	}
	fmt.Fprintln(streams.Stdout, "This project has Taskwarrior data to migrate, but no task binary was found.")
	fmt.Fprintln(streams.Stdout, "  [i] install Taskwarrior; the next run migrates")
	fmt.Fprintln(streams.Stdout, "  [p] proceed without the migration: a new, empty flow database; the")
	fmt.Fprintln(streams.Stdout, "      Taskwarrior data stays where it is, and migrating it later needs a")
	fmt.Fprintln(streams.Stdout, "      clean flow database")
	fmt.Fprint(streams.Stdout, "Choice [i/p]: ")
	answer, _ := bufio.NewReader(input).ReadString('\n')
	if choice := strings.ToLower(strings.TrimSpace(answer)); choice == "p" || choice == "proceed" {
		return 0
	}
	fmt.Fprintf(streams.Stderr, "ℹ Install Taskwarrior, then run jacazul flow again: %s\n", installHint(runtime.GOOS))
	return 1
}

func installHint(goos string) string {
	switch goos {
	case "darwin":
		return "brew install task"
	case "windows":
		return "Taskwarrior runs under WSL: install it there with your distribution's package manager"
	default:
		return "sudo dnf install task (Fedora) or sudo apt install taskwarrior (Debian, Ubuntu)"
	}
}

// migrate exports a temporary copy of silo with task and migrates it with
// flow.MigrateTaskwarrior: a dry-run, then the apply when apply is set.
// Taskwarrior may write to the directory it reads even for an export, so
// it only ever sees the copy, and with garbage collection, recurrence and
// hooks off. The copy is also where the engine reads focus, sessions and
// handoff notes, and the silo's canonical path is the origin the database
// records. The report goes to out.
//
// ERROR issues never stop the apply: every issue is printed, each naming
// its task, and an ACTION: sends the agent to them. Any other failure
// stops with the engine's own guidance and, for the apply, leaves no
// database behind, so the next run can try again.
func migrate(ctx context.Context, task, silo string, env flow.Env, out, stderr io.Writer, apply bool) int {
	fail := func(format string, a ...any) int {
		fmt.Fprintf(stderr, "❌ jacazul flow: "+format+"\n", a...)
		return 1
	}
	work, err := os.MkdirTemp("", "jacazul-migrate-")
	if err != nil {
		return fail("%v", err)
	}
	defer os.RemoveAll(work)

	copied := filepath.Join(work, "taskdata")
	if err := os.CopyFS(copied, os.DirFS(silo)); err != nil {
		return fail("copy %s: %v\nACTION: Check that the Taskwarrior data is readable and run jacazul flow again; it was not changed.", silo, err)
	}
	// The Jacazul taskrc declares the UDAs, so numeric ones export as
	// numbers, and no context or setting of the operator's own taskrc
	// filters the export.
	taskrc := filepath.Join(work, "taskrc")
	rc := dataLocation.ReplaceAllLiteralString(tasktmpl.Caged, "data.location="+copied)
	if err := os.WriteFile(taskrc, []byte(rc), 0o600); err != nil {
		return fail("%v", err)
	}
	cmd := exec.CommandContext(ctx, task, "rc.data.location="+copied,
		"rc.gc=off", "rc.recurrence=off", "rc.hooks=off", "rc.verbose=nothing", "rc.confirmation=off", "export")
	cmd.Env = append(os.Environ(), "TASKDATA="+copied, "TASKRC="+taskrc)
	var exported, taskErr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &exported, &taskErr
	if err := cmd.Run(); err != nil {
		return fail("Taskwarrior export failed: %v: %s\nACTION: Fix what task reports and run jacazul flow again; the Taskwarrior data was not changed.",
			err, strings.TrimSpace(taskErr.String()))
	}
	if !json.Valid(exported.Bytes()) {
		return fail("the Taskwarrior export is not valid JSON\nACTION: Run 'taskp export' to see what task prints, fix it and run jacazul flow again.")
	}
	export := filepath.Join(work, "export.json")
	if err := os.WriteFile(export, exported.Bytes(), 0o600); err != nil {
		return fail("%v", err)
	}

	options := flow.MigrateOptions{Source: export, Origin: canonical(silo), LegacyDataDir: copied}
	result, err := migrateEngine(ctx, env, options)
	if apply && (err == nil || errors.Is(err, flow.ErrMigrationRecordErrors)) {
		options.Apply = true
		result, err = migrateEngine(ctx, env, options)
	}
	if err != nil && !errors.Is(err, flow.ErrMigrationRecordErrors) {
		fmt.Fprintln(stderr, err)
		return 1
	}

	errs := 0
	for _, issue := range result.Issues {
		fmt.Fprintf(out, "%s: %s\n", issue.Severity, issue.Message)
		if issue.Severity == "ERROR" {
			errs++
		}
	}
	r := result.Records
	counts := fmt.Sprintf("created %d, updated %d, unchanged %d, dependencies %d, annotations %d, tags %d, issues %d",
		r.Created, r.Updated, r.Unchanged, r.Dependencies, r.Annotations, r.Tags, r.Issues)
	if apply {
		fmt.Fprintf(out, "🐊 jacazul flow: migrated %s into %s (%s)\n", silo, env.DatabasePath, counts)
	} else {
		fmt.Fprintf(out, "🐊 jacazul flow (dry): would migrate %s (%s); nothing is written\n", silo, counts)
	}
	if errs > 0 {
		fmt.Fprintf(out, "⚠️  jacazul flow: %d ERROR issues; the records were migrated as each line above says\n", errs)
		fmt.Fprintln(out, "ACTION: Check each task an ERROR line names (task <uuid>) in the Taskwarrior data and fix it in the flow database if it matters.")
	}
	return 0
}

// canonical is path made absolute with its symbolic links resolved, the one
// form the launcher records as a migration origin and compares with.
func canonical(path string) string {
	abs, err := filepath.Abs(path)
	if err != nil {
		return path
	}
	if resolved, err := filepath.EvalSymlinks(abs); err == nil {
		return resolved
	}
	return abs
}

func either(ok bool, yes, no string) string {
	if ok {
		return yes
	}
	return no
}

func exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func isTerminal(f *os.File) bool {
	info, err := f.Stat()
	return err == nil && info.Mode()&os.ModeCharDevice != 0
}
