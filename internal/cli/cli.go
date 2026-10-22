// Package cli holds the jacazul launcher commands. Each harness gets its
// own command file; Run parses the arguments and dispatches.
package cli

import (
	"cmp"
	"errors"
	"fmt"
	"io"
	"os"

	"github.com/jessevdk/go-flags"

	"github.com/jacazul-ai/launcher/internal/bootstrap/environment"
	"github.com/jacazul-ai/launcher/internal/bootstrap/project"
)

// Options are the flags accepted before the harness name. Everything after
// the harness name belongs to the harness.
type Options struct {
	Version bool   `short:"v" long:"version" description:"Print the launcher version and exit"`
	Dry     bool   `long:"dry" description:"Run every bootstrap step but do not start the harness (also DRY)"`
	Debug   bool   `long:"debug" description:"Print what each bootstrap step verifies (also DEBUG)"`
	Project string `long:"project" value-name:"ID" description:"Pin the project ID instead of resolving it from the working directory (also JACAZUL_PROJECT)"`
	Home    string `long:"home" value-name:"DIR" description:"Jacazul home directory (also JACAZUL_HOME; default ~/.jacazul-ai)"`
	Session string `long:"session" value-name:"ID" description:"Jacazul session ID (also JACAZUL_SESSION; default global)"`
	// LegacySession is the Bash launchers' name for --session, kept until
	// the cutoff.
	LegacySession string `long:"jacazul-session" value-name:"ID" hidden:"true"`
}

// Run executes the launcher with args (without the program name) and
// returns the process exit code.
func Run(args []string, stdout, stderr io.Writer, version string) int {
	var opts Options
	parser := flags.NewParser(&opts, flags.HelpFlag|flags.PassAfterNonOption)
	parser.Name = "jacazul"
	parser.Usage = "[Options] <harness> [args...]\n\nHarnesses:\n  claude    Claude Code\n\nCommands:\n  flow session list    List this project's Jacazul sessions\n  ui doctor            Audit browser automation servers (read-only)"

	rest, err := parser.ParseArgs(args)
	if opts.Version {
		fmt.Fprintln(stdout, version)
		return 0
	}
	if err != nil {
		var flagsErr *flags.Error
		if errors.As(err, &flagsErr) && flagsErr.Type == flags.ErrHelp {
			parser.WriteHelp(stdout)
			return 0
		}
		fmt.Fprintln(stderr, err)
		parser.WriteHelp(stderr)
		return 1
	}

	if len(rest) > 0 && rest[0] == "claude" {
		return runClaude(opts, rest[1:], stdout, stderr)
	}
	if len(rest) > 0 && rest[0] == "flow" {
		return runFlow(opts, rest[1:], stdout, stderr)
	}
	if len(rest) > 0 && rest[0] == "ui" {
		return runUI(rest[1:], stdout, stderr)
	}
	if len(rest) == 0 {
		fmt.Fprintln(stderr, "no harness given")
	} else {
		fmt.Fprintf(stderr, "unknown harness %q\n", rest[0])
	}
	parser.WriteHelp(stderr)
	return 1
}

// resolveProject is the project: --project, then JACAZUL_PROJECT, then the
// canonical resolution of dir. An override pins the ID only; the anchor
// still comes from dir.
func resolveProject(flag, dir string) (project.Identity, error) {
	id, err := project.Resolve(dir)
	if err != nil {
		return id, err
	}
	id.ID = cmp.Or(flag, os.Getenv("JACAZUL_PROJECT"), id.ID)
	return id, nil
}

// sessionFor is the session the bootstraps that still speak tw-flow's
// language see: the global session is no independent session, so it reads
// as "" there and tw-flow keeps the global focus.json.
func sessionFor(id string) string {
	if id == environment.Global {
		return ""
	}
	return id
}
