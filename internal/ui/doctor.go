// Package ui audits the browser automation servers on this machine: which
// ones run, how they were started, who started them and what debugging
// ports stay open. It only reads; every fix is printed for the operator.
package ui

import (
	"fmt"
	"io"
	"path/filepath"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/jacazul-ai/launcher/internal/session"
)

// Process is one running process. Command is the full command line with
// its arguments separated by spaces; Age is zero when the source cannot
// tell it.
type Process struct {
	PID     int
	PPID    int
	Age     time.Duration
	Command string
}

// Listener is a TCP port in the LISTEN state. PID is zero when the owner
// is not visible to the current user.
type Listener struct {
	Port int
	PID  int
}

// Snapshot is everything the doctor reads from the machine.
type Snapshot struct {
	Processes []Process
	Listeners []Listener
	// Chromium is the path of a dedicated Chromium, "" when none was found.
	Chromium string
}

// Server is a browser automation server process and what is wrong with it.
type Server struct {
	Process
	// Parent is the parent's program name, "" when the parent is gone.
	Parent   string
	Orphan   bool
	Problems []string
}

// Debugger is a browser debugging endpoint: a process started with
// --remote-debugging-port, a listener on a well-known debugging port, or
// both. PID is zero and Command empty when the owner is not visible.
type Debugger struct {
	PID     int
	Port    int
	Command string
}

// Report is the doctor's verdict.
type Report struct {
	Servers   []Server
	Debuggers []Debugger
	Chromium  string
}

// Clean reports whether nothing needs the operator: no server with a
// problem, no orphan, no open debugging port.
func (r Report) Clean() bool {
	for _, s := range r.Servers {
		if s.Orphan || len(s.Problems) > 0 {
			return false
		}
	}
	return len(r.Debuggers) == 0
}

// serverToken matches an argument that runs chrome-devtools-mcp: the bare
// package name, the package at a version, or a path to its executable.
var serverToken = regexp.MustCompile(`^(?:.*[/\\])?chrome-devtools-mcp(?:@(\S+))?$|[/\\]node_modules[/\\]chrome-devtools-mcp[/\\]`)

// Flag spellings the server accepts for each capability. Only the
// spellings listed here count; anything else reads as missing.
var (
	attachFlags   = []string{"--wsEndpoint", "--ws-endpoint", "-w", "--browserUrl", "--browser-url", "-u", "--autoConnect", "--auto-connect"}
	required      = []string{"--executablePath", "--isolated", "--headless", "--no-usage-statistics", "--no-performance-crux"}
	requiredAlias = map[string][]string{
		"--executablePath":      {"--executablePath", "--executable-path", "-e"},
		"--isolated":            {"--isolated"},
		"--headless":            {"--headless"},
		"--no-usage-statistics": {"--no-usage-statistics", "--no-usageStatistics", "--usageStatistics=false", "--usage-statistics=false"},
		"--no-performance-crux": {"--no-performance-crux", "--no-performanceCrux", "--performanceCrux=false", "--performance-crux=false"},
	}
)

// debugPorts are the ports a browser's DevTools endpoint usually listens on.
func debugPort(port int) bool { return port >= 9222 && port <= 9229 }

// Diagnose turns a snapshot into a report. It is pure: everything it knows
// comes from s.
func Diagnose(s Snapshot) Report {
	byPID := make(map[int]Process, len(s.Processes))
	for _, p := range s.Processes {
		byPID[p.PID] = p
	}

	r := Report{Chromium: s.Chromium}
	for _, p := range s.Processes {
		args := splitCommand(p.Command)
		version, ok := serverVersion(args)
		if !ok {
			continue
		}
		srv := Server{Process: p}
		parent, alive := byPID[p.PPID]
		srv.Parent = program(parent.Command)
		// A process whose parent exits is adopted by init or by a
		// subreaper such as systemd --user; either way its session is gone.
		if !alive || p.PPID <= 1 || slices.Contains(adopters, srv.Parent) {
			srv.Orphan = true
		}
		if strings.Contains(p.Command, "watchdog") {
			srv.Problems = []string{"telemetry watchdog running: its server was started without --no-usage-statistics"}
		} else {
			srv.Problems = launchProblems(args, version)
		}
		r.Servers = append(r.Servers, srv)
	}

	seen := map[Debugger]bool{}
	for _, p := range s.Processes {
		if port, ok := debuggingFlag(strings.Fields(p.Command)); ok {
			d := Debugger{PID: p.PID, Port: port, Command: p.Command}
			r.Debuggers = append(r.Debuggers, d)
			seen[Debugger{PID: p.PID, Port: port}] = true
		}
	}
	for _, l := range s.Listeners {
		if !debugPort(l.Port) || seen[Debugger{PID: l.PID, Port: l.Port}] {
			continue
		}
		r.Debuggers = append(r.Debuggers, Debugger{PID: l.PID, Port: l.Port, Command: byPID[l.PID].Command})
	}
	return r
}

// launchers are the programs that run a Node package. The server is the
// program itself or the package one of these runs; a shell or an editor
// whose arguments merely name it is not the server.
var launchers = []string{"npx", "npm", "pnpm", "pnpx", "yarn", "bunx", "bun", "node", "nodejs", "deno"}

// adopters are the processes that inherit orphans.
var adopters = []string{"init", "systemd", "launchd"}

// serverVersion finds the argument that runs the server. version is the
// pinned version, "latest", "" for the bare package name, or "path" when
// the server runs from an installed path that does not show it.
func serverVersion(args []string) (version string, ok bool) {
	if len(args) == 0 {
		return "", false
	}
	candidates := args[:1]
	if slices.Contains(launchers, programName(args[0])) {
		candidates = args[1:]
	}
	for _, a := range candidates {
		m := serverToken.FindStringSubmatch(a)
		if m == nil {
			continue
		}
		switch {
		case m[1] != "":
			return m[1], true
		case strings.ContainsAny(a, `/\`):
			return "path", true
		default:
			return "", true
		}
	}
	return "", false
}

func launchProblems(args []string, version string) []string {
	var problems []string
	for _, a := range args {
		name, _, _ := strings.Cut(a, "=")
		if slices.Contains(attachFlags, name) && !strings.HasSuffix(a, "=false") {
			problems = append(problems, fmt.Sprintf("attach mode (%s): the server drives a browser it did not launch", name))
		}
		if name == "--config" {
			problems = append(problems, "flags from --config: the doctor cannot read the file; check it for attach flags")
		}
	}
	switch {
	case version == "latest":
		problems = append(problems, "unpinned (@latest): pin an exact version at least 7 days old")
	case version == "":
		problems = append(problems, "unpinned (no version): pin an exact version at least 7 days old")
	case version != "path" && (version[0] < '0' || version[0] > '9'):
		problems = append(problems, fmt.Sprintf("unpinned (@%s): pin an exact version at least 7 days old", version))
	}
	for _, flag := range required {
		if !hasFlag(args, requiredAlias[flag]) {
			problems = append(problems, "missing "+flag)
		}
	}
	return problems
}

// hasFlag reports whether one of the spellings is present and not turned
// off: --isolated and --isolated=true count, --isolated=false does not.
func hasFlag(args, spellings []string) bool {
	for _, a := range args {
		if slices.Contains(spellings, a) {
			return true
		}
		name, value, _ := strings.Cut(a, "=")
		if slices.Contains(spellings, name) && value != "false" {
			return true
		}
	}
	return false
}

// debuggingFlag finds --remote-debugging-port=N or --remote-debugging-port N.
func debuggingFlag(args []string) (int, bool) {
	for i, a := range args {
		name, value, hasValue := strings.Cut(a, "=")
		if name != "--remote-debugging-port" {
			continue
		}
		if !hasValue && i+1 < len(args) {
			value = args[i+1]
		}
		if port, err := strconv.Atoi(value); err == nil && port > 0 {
			return port, true
		}
	}
	return 0, false
}

// splitCommand splits a command line on spaces, keeping a quoted program
// path whole, as Windows writes "C:\Program Files\...\node.exe".
func splitCommand(command string) []string {
	if rest, ok := strings.CutPrefix(command, `"`); ok {
		if first, after, found := strings.Cut(rest, `"`); found {
			return append([]string{first}, strings.Fields(after)...)
		}
	}
	return strings.Fields(command)
}

// program is the bare, lowercase name of a command's program: no
// directory and no Windows executable suffix.
func program(command string) string {
	args := splitCommand(command)
	if len(args) == 0 {
		return ""
	}
	return programName(args[0])
}

func programName(path string) string {
	name := strings.ToLower(filepath.Base(strings.ReplaceAll(path, `\`, "/")))
	for _, suffix := range []string{".exe", ".cmd"} {
		name = strings.TrimSuffix(name, suffix)
	}
	return name
}

// Write prints the report and the commands the operator may run. goos picks
// the command syntax; nothing is executed.
func Write(w io.Writer, r Report, goos string) {
	fmt.Fprintln(w, "🐊 UI DOCTOR (read-only: nothing was changed)")

	var kill []int
	if len(r.Servers) == 0 {
		fmt.Fprintln(w, "✓ No browser automation server running.")
	}
	for _, s := range r.Servers {
		age := "age unknown"
		if s.Age > 0 {
			age = "age " + session.FormatAge(s.Age)
		}
		parent := fmt.Sprintf("parent %d (%s)", s.PPID, s.Parent)
		switch {
		case s.Orphan && s.Parent != "":
			parent = fmt.Sprintf("orphan adopted by %d (%s)", s.PPID, s.Parent)
		case s.Orphan:
			parent = fmt.Sprintf("orphan: parent %d gone", s.PPID)
		}
		mark := "✓"
		if s.Orphan || len(s.Problems) > 0 {
			mark = "✗"
			kill = append(kill, s.PID)
		}
		fmt.Fprintf(w, "%s PID %d, %s, %s\n    %s\n", mark, s.PID, age, parent, s.Command)
		for _, p := range s.Problems {
			fmt.Fprintf(w, "    - %s\n", p)
		}
	}

	if len(r.Debuggers) == 0 {
		fmt.Fprintln(w, "✓ No remote-debugging port open.")
	}
	for _, d := range r.Debuggers {
		owner := "owner not visible to this user"
		if d.PID != 0 {
			owner = fmt.Sprintf("PID %d: %s", d.PID, d.Command)
		}
		fmt.Fprintf(w, "✗ Debugging port %d open (%s)\n", d.Port, owner)
	}

	if r.Chromium == "" {
		fmt.Fprintln(w, "⚠ No dedicated Chromium found: install one for automation and pass it with --executablePath.")
	} else {
		fmt.Fprintf(w, "✓ Dedicated Chromium: %s\n", r.Chromium)
	}

	if len(kill) == 0 && len(r.Debuggers) == 0 {
		return
	}
	fmt.Fprintln(w, "\nNext steps (run only after you confirm each one):")
	for _, pid := range kill {
		if goos == "windows" {
			fmt.Fprintf(w, "  Stop-Process -Id %d\n", pid)
		} else {
			fmt.Fprintf(w, "  kill %d\n", pid)
		}
	}
	if len(r.Debuggers) > 0 {
		fmt.Fprintln(w, "  Close each browser holding a debugging port and start it again without --remote-debugging-port.")
	}
	fmt.Fprintln(w, "  Fix the configuration that starts these servers (ui-expert, references/browser-safety.md), or they come back next session.")
}
