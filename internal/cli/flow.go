package cli

import (
	"cmp"
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"time"

	"github.com/jacazul-ai/flow"

	"github.com/jacazul-ai/launcher/internal/bootstrap/environment"
	"github.com/jacazul-ai/launcher/internal/session"
)

// flowRunner runs one command of the embedded workflow engine.
type flowRunner func(context.Context, []string, flow.Env, flow.Streams) int

// runEngine is the embedded engine; tests replace it.
var runEngine flowRunner = flow.Run

// runFlow answers session list natively, from the Taskwarrior lanes, and
// runs every other command in the embedded engine.
func runFlow(opts Options, args []string, stdout, stderr io.Writer) int {
	if len(args) == 2 && args[0] == "session" && args[1] == "list" {
		return sessionList(opts, stdout, stderr)
	}
	return engine(opts, args, stdout, stderr)
}

// engine runs args in the embedded engine with the context the launcher
// resolved, and returns the engine's exit status. The engine's output,
// ACTION: guidance included, reaches the operator unchanged. Before any
// command but migrate, opening the project settles its storage.
//
// The flow database lives under ~/.jacazul/projects; --home and
// JACAZUL_HOME still name the legacy runtime home, whose .task silo is
// only read.
func engine(opts Options, args []string, stdout, stderr io.Writer) int {
	cwd, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(stderr, "❌ jacazul flow: %v\n", err)
		return 1
	}
	id, err := resolveProject(opts.Project, cwd)
	if err != nil {
		fmt.Fprintf(stderr, "❌ jacazul flow: %v\n", err)
		return 1
	}
	home := filepath.Join(os.Getenv("HOME"), ".jacazul")
	env := flow.Env{
		ProjectID: id.ID,
		SessionID: environment.Session(cmp.Or(opts.Session, opts.LegacySession), os.Getenv),
		Home:      home,
		DatabasePath: cmp.Or(os.Getenv("JACAZUL_FLOW_DATABASE_PATH"),
			filepath.Join(home, "projects", id.ID, "flow.sqlite3")),
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	streams := flow.Streams{Stdin: os.Stdin, Stdout: stdout, Stderr: stderr}

	if len(args) > 0 && args[0] != "migrate" {
		// A launcher outside a checkout finds task on PATH all the same.
		root, _ := checkout()
		silo := filepath.Join(environment.Home(opts.Home, os.Getenv), ".task", id.ID)
		if code := openStorage(ctx, root, silo, env, streams); code != 0 {
			return code
		}
	}
	return runEngine(ctx, args, env, streams)
}

// sessionList prints the project's independent session lanes like
// tw-flow session list, plus whether a handoff note waits for each. An
// inherited TASKDATA names the lanes' directory unless --project or --home
// asks for another one.
func sessionList(opts Options, stdout, stderr io.Writer) int {
	dir := os.Getenv("TASKDATA")
	if dir == "" || opts.Project != "" || opts.Home != "" || os.Getenv("JACAZUL_PROJECT") != "" {
		cwd, err := os.Getwd()
		if err != nil {
			fmt.Fprintf(stderr, "❌ jacazul flow: %v\n", err)
			return 1
		}
		id, err := resolveProject(opts.Project, cwd)
		if err != nil {
			fmt.Fprintf(stderr, "❌ jacazul flow: %v\n", err)
			return 1
		}
		dir = filepath.Join(environment.Home(opts.Home, os.Getenv), ".task", id.ID)
	}
	sessions, err := session.List(dir, time.Now())
	if err != nil {
		fmt.Fprintf(stderr, "❌ jacazul flow: %v\n", err)
		return 1
	}
	if len(sessions) == 0 {
		fmt.Fprintln(stdout, "ℹ No independent sessions found.")
		return 0
	}

	current := environment.Session(cmp.Or(opts.Session, opts.LegacySession), os.Getenv)
	// The header and the lanes share one layout, so the columns line up.
	const layout = "%-12s%-30s %-10s %-7s %-7s %s"
	fmt.Fprintf(stdout, layout+"\n", "SESSION", "PLAN", "TASK", "AGE", "STATUS", "HANDOFF")
	fmt.Fprintln(stdout, strings.Repeat("-", 78))
	for _, s := range sessions {
		marker := " "
		if s.ID == current {
			marker = "*"
		}
		line := fmt.Sprintf(layout,
			s.ID+" "+marker, s.Plan, s.Task, session.FormatAge(s.Age), s.Status, s.Handoff)
		fmt.Fprintln(stdout, strings.TrimRight(line, " "))
	}
	return 0
}
