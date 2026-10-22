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

// runFlow holds the workflow commands the launcher answers natively and
// sends migrate to the embedded engine. Everything else stays with tw-flow
// until opening a project decides its storage.
func runFlow(opts Options, args []string, stdout, stderr io.Writer) int {
	if len(args) == 2 && args[0] == "session" && args[1] == "list" {
		return sessionList(opts, stdout, stderr)
	}
	if len(args) > 0 && args[0] == "migrate" {
		return engine(opts, args, stdout, stderr)
	}
	fmt.Fprintf(stderr, "❌ jacazul flow: only 'session list' and 'migrate' run here for now; run 'tw-flow %s'\n", strings.Join(args, " "))
	return 1
}

// engine runs args in the embedded engine with the context the launcher
// resolved, and returns the engine's exit status. The engine's output,
// ACTION: guidance included, reaches the operator unchanged.
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
	env := flow.Env{
		ProjectID:    id.ID,
		SessionID:    environment.Session(cmp.Or(opts.Session, opts.LegacySession), os.Getenv),
		Home:         environment.Home(opts.Home, os.Getenv),
		DatabasePath: os.Getenv("JACAZUL_FLOW_DATABASE_PATH"),
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	return runEngine(ctx, args, env, flow.Streams{Stdin: os.Stdin, Stdout: stdout, Stderr: stderr})
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
