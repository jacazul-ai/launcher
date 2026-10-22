package ui

import (
	"bytes"
	"slices"
	"strings"
	"testing"
	"time"
)

// safe is the reference launch: a pinned server that starts its own
// isolated, headless browser and sends nothing out.
const safe = "npx -y chrome-devtools-mcp@1.10.1 --executablePath /usr/bin/chromium-browser --isolated --headless --no-usage-statistics --no-performance-crux"

func TestASafeServerUnderALiveParentIsClean(t *testing.T) {
	r := Diagnose(Snapshot{
		Processes: []Process{
			{PID: 100, PPID: 1, Command: "pi"},
			{PID: 200, PPID: 100, Age: time.Hour, Command: safe},
		},
		Chromium: "/usr/bin/chromium-browser",
	})
	if len(r.Servers) != 1 {
		t.Fatalf("servers %+v, want the one server", r.Servers)
	}
	if s := r.Servers[0]; len(s.Problems) != 0 || s.Orphan || s.Parent != "pi" {
		t.Errorf("server %+v, want no problems under parent pi", s)
	}
	if !r.Clean() {
		t.Error("report not clean")
	}
}

func TestEveryUnsafeLaunchIsNamed(t *testing.T) {
	for name, tc := range map[string]struct {
		command string
		want    string
	}{
		"ws endpoint":       {"npx -y chrome-devtools-mcp@1.10.1 --wsEndpoint=ws://127.0.0.1:9222/devtools/browser", "attach mode (--wsEndpoint)"},
		"ws endpoint kebab": {"npx -y chrome-devtools-mcp@1.10.1 --ws-endpoint ws://127.0.0.1:9222", "attach mode (--ws-endpoint)"},
		"browser url alias": {"npx -y chrome-devtools-mcp@1.10.1 -u http://127.0.0.1:9222", "attach mode (-u)"},
		"auto connect":      {"npx -y chrome-devtools-mcp@1.10.1 --autoConnect", "attach mode (--autoConnect)"},
		"latest":            {"npx -y chrome-devtools-mcp@latest --isolated", "unpinned (@latest)"},
		"no version":        {"npx -y chrome-devtools-mcp --isolated", "unpinned (no version)"},
		"no executable":     {"npx -y chrome-devtools-mcp@1.10.1 --isolated", "missing --executablePath"},
		"no isolated":       {"npx -y chrome-devtools-mcp@1.10.1 --headless", "missing --isolated"},
		"isolated off":      {"npx -y chrome-devtools-mcp@1.10.1 --isolated=false", "missing --isolated"},
		"no headless":       {"npx -y chrome-devtools-mcp@1.10.1 --isolated", "missing --headless"},
		"telemetry":         {"npx -y chrome-devtools-mcp@1.10.1 --isolated", "missing --no-usage-statistics"},
		"crux":              {"npx -y chrome-devtools-mcp@1.10.1 --isolated", "missing --no-performance-crux"},
		"config file":       {"npx -y chrome-devtools-mcp@1.10.1 --config /tmp/c.json", "flags from --config"},
	} {
		t.Run(name, func(t *testing.T) {
			r := Diagnose(Snapshot{Processes: []Process{
				{PID: 100, PPID: 1, Command: "pi"},
				{PID: 200, PPID: 100, Command: tc.command},
			}})
			if len(r.Servers) != 1 {
				t.Fatalf("servers %+v, want one", r.Servers)
			}
			if !hasPrefix(r.Servers[0].Problems, tc.want) {
				t.Errorf("problems %q, want one starting with %q", r.Servers[0].Problems, tc.want)
			}
			if r.Clean() {
				t.Error("report clean")
			}
		})
	}
}

func TestEquivalentFlagSpellingsCount(t *testing.T) {
	command := "node /home/u/.npm/_npx/ab12/node_modules/chrome-devtools-mcp/build/src/index.js -e /usr/bin/chromium --isolated --headless=true --usageStatistics=false --performance-crux=false"
	r := Diagnose(Snapshot{Processes: []Process{
		{PID: 100, PPID: 1, Command: "pi"},
		{PID: 200, PPID: 100, Command: command},
	}})
	if len(r.Servers) != 1 || len(r.Servers[0].Problems) != 0 {
		t.Fatalf("servers %+v, want one without problems: the path form hides the version", r.Servers)
	}
}

func TestServersRunByEveryLauncherAreFound(t *testing.T) {
	for _, command := range []string{
		"npx -y chrome-devtools-mcp@1.10.1",
		"npm exec chrome-devtools-mcp@1.10.1",
		"pnpm dlx chrome-devtools-mcp@1.10.1",
		"bunx chrome-devtools-mcp@1.10.1",
		"/usr/bin/node /x/node_modules/.bin/chrome-devtools-mcp",
		`"C:\Program Files\nodejs\node.exe" C:\x\node_modules\chrome-devtools-mcp\build\src\index.js`,
		`"C:\Program Files\nodejs\npx.cmd" -y chrome-devtools-mcp@1.10.1`,
		"/home/u/.local/bin/chrome-devtools-mcp --isolated",
	} {
		r := Diagnose(Snapshot{Processes: []Process{{PID: 200, PPID: 1, Command: command}}})
		if len(r.Servers) != 1 {
			t.Errorf("%q: servers %+v, want one", command, r.Servers)
		}
	}
}

func TestOrphansAreFlagged(t *testing.T) {
	for name, ppid := range map[string]int{"reparented to init": 1, "parent gone": 4242, "reparented to a user subreaper": 3462} {
		t.Run(name, func(t *testing.T) {
			r := Diagnose(Snapshot{Processes: []Process{
				{PID: 3462, PPID: 1, Command: "/usr/lib/systemd/systemd --user"},
				{PID: 200, PPID: ppid, Command: safe},
			}})
			if len(r.Servers) != 1 || !r.Servers[0].Orphan {
				t.Fatalf("servers %+v, want an orphan", r.Servers)
			}
			if r.Clean() {
				t.Error("an orphan left the report clean")
			}
		})
	}
}

func TestTheTelemetryWatchdogIsItsOwnFinding(t *testing.T) {
	r := Diagnose(Snapshot{Processes: []Process{
		{PID: 100, PPID: 1, Command: "pi"},
		{PID: 200, PPID: 100, Command: safe},
		{PID: 300, PPID: 200, Command: "node /x/node_modules/chrome-devtools-mcp/build/src/telemetry/watchdog/main.js --parent-pid=200"},
	}})
	if len(r.Servers) != 2 {
		t.Fatalf("servers %+v, want the server and its watchdog", r.Servers)
	}
	watchdog := r.Servers[1]
	if want := []string{"telemetry watchdog running: its server was started without --no-usage-statistics"}; !slices.Equal(watchdog.Problems, want) {
		t.Errorf("watchdog problems %q, want %q", watchdog.Problems, want)
	}
}

func TestCommandsThatOnlyMentionTheServerAreIgnored(t *testing.T) {
	r := Diagnose(Snapshot{Processes: []Process{
		{PID: 100, PPID: 1, Command: "/bin/zsh -c pgrep -af chrome-devtools-mcp'"},
		{PID: 101, PPID: 1, Command: "grep chrome-devtools-mcp-notes.txt"},
		{PID: 102, PPID: 1, Command: "jacazul ui doctor"},
		// A shell whose script names the server is not the server; offering
		// to kill it would kill the harness's own shell.
		{PID: 103, PPID: 1, Command: "bash -c (exec -a chrome-devtools-mcp@latest sleep 15 &); sleep 1"},
		{PID: 104, PPID: 1, Command: "vim notes/chrome-devtools-mcp"},
	}})
	if len(r.Servers) != 0 {
		t.Errorf("servers %+v, want none", r.Servers)
	}
}

func TestDebuggingPortsAreReported(t *testing.T) {
	r := Diagnose(Snapshot{
		Processes: []Process{
			{PID: 500, PPID: 1, Command: "/usr/bin/brave --remote-debugging-port=9222"},
			{PID: 600, PPID: 1, Command: "/usr/bin/other-browser --remote-debugging-port 9333"},
		},
		Listeners: []Listener{{Port: 9222, PID: 500}, {Port: 9223, PID: 0}, {Port: 8080, PID: 700}},
	})
	want := []Debugger{
		{PID: 500, Port: 9222, Command: "/usr/bin/brave --remote-debugging-port=9222"},
		{PID: 600, Port: 9333, Command: "/usr/bin/other-browser --remote-debugging-port 9333"},
		{PID: 0, Port: 9223},
	}
	if !slices.Equal(r.Debuggers, want) {
		t.Errorf("debuggers %+v, want %+v", r.Debuggers, want)
	}
	if r.Clean() {
		t.Error("an open debugging port left the report clean")
	}
}

func TestWritePrintsCommandsWithoutRunningThem(t *testing.T) {
	r := Diagnose(Snapshot{
		Processes: []Process{
			{PID: 200, PPID: 1, Age: 50 * time.Hour, Command: "npx -y chrome-devtools-mcp@1.10.1 --wsEndpoint=ws://127.0.0.1:9222"},
			{PID: 500, PPID: 1, Command: "/usr/bin/brave --remote-debugging-port=9222"},
		},
		Listeners: []Listener{{Port: 9222, PID: 500}},
	})
	for goos, kill := range map[string]string{"linux": "kill 200", "darwin": "kill 200", "windows": "Stop-Process -Id 200"} {
		var out bytes.Buffer
		Write(&out, r, goos)
		text := out.String()
		for _, want := range []string{"PID 200", "2d", "orphan", "attach mode (--wsEndpoint)", "port 9222", kill, "No dedicated Chromium found"} {
			if !strings.Contains(text, want) {
				t.Errorf("%s: output lacks %q:\n%s", goos, want, text)
			}
		}
		if strings.Contains(text, "kill 500") || strings.Contains(text, "Stop-Process -Id 500") {
			t.Errorf("%s: output offers to kill the browser holding the port:\n%s", goos, text)
		}
	}
}

func TestWriteSaysCleanWhenClean(t *testing.T) {
	var out bytes.Buffer
	Write(&out, Diagnose(Snapshot{Chromium: "/usr/bin/chromium"}), "linux")
	for _, want := range []string{"No browser automation server running", "No remote-debugging port open", "/usr/bin/chromium"} {
		if !strings.Contains(out.String(), want) {
			t.Errorf("output lacks %q:\n%s", want, out.String())
		}
	}
}

func hasPrefix(lines []string, prefix string) bool {
	return slices.ContainsFunc(lines, func(l string) bool { return strings.HasPrefix(l, prefix) })
}
