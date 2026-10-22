package cli

import (
	"bufio"
	"bytes"
	"cmp"
	"context"
	"encoding/json"
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

// opensStorage reports whether the engine command opens the project's
// storage; help, version and info do not, so they trigger no migration.
func opensStorage(args []string) bool {
	return len(args) > 0 && !slices.Contains([]string{"info", "help", "--help", "-h", "--version"}, args[0])
}

// openStorage settles the project's storage before an engine command, as
// "Opening a project" in docs/ARCHITECTURE.md lays out: an existing flow
// database is used, a Taskwarrior silo is migrated, and nothing at all
// means a new database. It returns non-zero when the command must not run.
// The silo is only ever read.
//
// A dry run prints the locations and the decision, runs the migration as
// a dry-run, and writes nothing.
func openStorage(ctx context.Context, root, silo string, env flow.Env, streams flow.Streams, dry bool) int {
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
	if dry {
		fmt.Fprintln(streams.Stdout, "🐊 jacazul flow (dry): nothing is written")
		fmt.Fprintf(streams.Stdout, "   database  %s (%s)\n", env.DatabasePath, either(found, "exists", "missing"))
		fmt.Fprintf(streams.Stdout, "   silo      %s (%s)\n", silo, either(data, "Taskwarrior data", "no Taskwarrior data"))
		if !found && data {
			fmt.Fprintf(streams.Stdout, "   task      %s\n", cmp.Or(task, "not found"))
		}
		fmt.Fprintf(streams.Stdout, "   action    %s\n", action)
	}

	switch {
	case found || !data:
		return 0
	case task == "" && dry:
		return 0
	case task == "":
		return askWithoutTask(streams)
	case dry:
		return migrate(ctx, task, silo, env, streams, []string{"migrate", "taskwarrior", "--dry-run"})
	}
	// The migration report goes to stderr, so the output of the command
	// that triggered it stays clean for whoever reads it.
	report := flow.Streams{Stdin: streams.Stdin, Stdout: streams.Stderr, Stderr: streams.Stderr}
	fmt.Fprintf(streams.Stderr, "🔄 jacazul flow: migrating %s into %s\n", silo, env.DatabasePath)
	return migrate(ctx, task, silo, env, report, []string{"migrate", "taskwarrior", "--apply"})
}

// explicitMigration reports whether args ask the engine to migrate
// Taskwarrior data that jacazul must export first: no --source snapshot
// and no --issues listing.
func explicitMigration(args []string) bool {
	if len(args) < 2 || args[0] != "migrate" || args[1] != "taskwarrior" {
		return false
	}
	for _, arg := range args[2:] {
		if arg == "--issues" || arg == "--source" || strings.HasPrefix(arg, "--source=") {
			return false
		}
	}
	return true
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

// migrate exports a temporary copy of silo with task and runs the
// engine's migration args on the export. Taskwarrior may write to the
// directory it reads even for an export, so it only ever sees the copy,
// and with garbage collection, recurrence and hooks off. A failed apply
// leaves no database behind, so the next run can try again.
func migrate(ctx context.Context, task, silo string, env flow.Env, streams flow.Streams, args []string) int {
	fail := func(format string, a ...any) int {
		fmt.Fprintf(streams.Stderr, "❌ jacazul flow: "+format+"\n", a...)
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
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	if err := cmd.Run(); err != nil {
		return fail("Taskwarrior export failed: %v: %s\nACTION: Fix what task reports and run jacazul flow again; the Taskwarrior data was not changed.",
			err, strings.TrimSpace(stderr.String()))
	}
	if !json.Valid(stdout.Bytes()) {
		return fail("the Taskwarrior export is not valid JSON\nACTION: Run 'taskp export' to see what task prints, fix it and run jacazul flow again.")
	}
	export := filepath.Join(work, "export.json")
	if err := os.WriteFile(export, stdout.Bytes(), 0o600); err != nil {
		return fail("%v", err)
	}

	args = append(slices.Clip(args), "--source", export)
	if !slices.ContainsFunc(args, func(a string) bool { return strings.HasPrefix(a, "--legacy-data-dir") }) {
		args = append(args, "--legacy-data-dir", copied)
	}
	created := !exists(env.DatabasePath)
	code := runEngine(ctx, args, env, streams)
	if code != 0 && created && slices.Contains(args, "--apply") {
		for _, suffix := range []string{"", "-wal", "-shm", "-journal"} {
			os.Remove(env.DatabasePath + suffix)
		}
	}
	return code
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
