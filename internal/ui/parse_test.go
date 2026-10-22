package ui

import (
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"
)

// fakeProc writes the parts of a Linux /proc tree the doctor reads.
func fakeProc(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	write := func(name, content string) {
		t.Helper()
		path := filepath.Join(root, name)
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	write("uptime", "1000.50 4000.00\n")
	// A comm with a space and a parenthesis, as the kernel allows.
	write("123/stat", "123 (npm exec (x) y) S 100 123 123 0 -1 4194560 1 0 0 0 0 0 0 0 20 0 1 0 50 0 0\n")
	write("123/cmdline", "npx\x00-y\x00chrome-devtools-mcp@1.10.1\x00--isolated\x00")
	write("100/stat", "100 (pi) S 1 100 100 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 10 0 0\n")
	write("100/cmdline", "pi\x00")
	// A kernel thread has an empty cmdline and is skipped.
	write("2/stat", "2 (kthreadd) S 0 0 0 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 1 0 0\n")
	write("2/cmdline", "")
	write("net/tcp", "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"+
		"   0: 0100007F:2406 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 55555 1\n"+
		"   1: 0100007F:1F90 0100007F:9C40 01 00000000:00000000 00:00000000 00000000  1000        0 66666 1\n")
	write("net/tcp6", "  sl  local_address rem_address   st\n"+
		"   0: 00000000000000000000000000000000:2407 00000000000000000000000000000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 77777 1\n")
	if err := os.MkdirAll(filepath.Join(root, "123", "fd"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("socket:[55555]", filepath.Join(root, "123", "fd", "3")); err != nil {
		t.Fatal(err)
	}
	return root
}

func TestReadProcFindsProcessesAndListeners(t *testing.T) {
	s, err := readProc(fakeProc(t))
	if err != nil {
		t.Fatal(err)
	}
	slices.SortFunc(s.Processes, func(a, b Process) int { return a.PID - b.PID })
	want := []Process{
		{PID: 100, PPID: 1, Age: 1000400 * time.Millisecond, Command: "pi"},
		{PID: 123, PPID: 100, Age: 1000000 * time.Millisecond, Command: "npx -y chrome-devtools-mcp@1.10.1 --isolated"},
	}
	if !slices.Equal(s.Processes, want) {
		t.Errorf("processes %+v, want %+v", s.Processes, want)
	}
	wantListeners := []Listener{{Port: 9222, PID: 123}, {Port: 9223, PID: 0}}
	if !slices.Equal(s.Listeners, wantListeners) {
		t.Errorf("listeners %+v, want %+v", s.Listeners, wantListeners)
	}
}

func TestParsePSReadsEveryElapsedForm(t *testing.T) {
	out := "    1     0 12-01:02:03 /sbin/launchd\n" +
		"  200     1    01:02:03 npx -y chrome-devtools-mcp@1.10.1 --isolated\n" +
		"  300   200       02:03 node watchdog\n" +
		"garbage line\n"
	got := parsePS(out)
	want := []Process{
		{PID: 1, PPID: 0, Age: 12*24*time.Hour + time.Hour + 2*time.Minute + 3*time.Second, Command: "/sbin/launchd"},
		{PID: 200, PPID: 1, Age: time.Hour + 2*time.Minute + 3*time.Second, Command: "npx -y chrome-devtools-mcp@1.10.1 --isolated"},
		{PID: 300, PPID: 200, Age: 2*time.Minute + 3*time.Second, Command: "node watchdog"},
	}
	if !slices.Equal(got, want) {
		t.Errorf("got %+v, want %+v", got, want)
	}
}

func TestParseLsofReadsFieldOutput(t *testing.T) {
	out := "p500\nf12\nn127.0.0.1:9222\nf13\nn[::1]:9222\np600\nf3\nn*:8080\n"
	want := []Listener{{Port: 9222, PID: 500}, {Port: 8080, PID: 600}}
	if got := parseLsof(out); !slices.Equal(got, want) {
		t.Errorf("got %+v, want %+v", got, want)
	}
}

func TestParseWindowsJSONAcceptsArrayAndSingleObject(t *testing.T) {
	procs, err := parseWindowsProcesses(`[{"ProcessId":4,"ParentProcessId":0,"CommandLine":null,"Age":100},` +
		`{"ProcessId":200,"ParentProcessId":4,"CommandLine":"npx -y chrome-devtools-mcp@1.10.1","Age":60}]`)
	if err != nil {
		t.Fatal(err)
	}
	want := []Process{
		{PID: 4, PPID: 0, Age: 100 * time.Second},
		{PID: 200, PPID: 4, Age: time.Minute, Command: "npx -y chrome-devtools-mcp@1.10.1"},
	}
	if !slices.Equal(procs, want) {
		t.Errorf("processes %+v, want %+v", procs, want)
	}

	listeners, err := parseWindowsListeners(`{"LocalPort":9222,"OwningProcess":500}`)
	if err != nil {
		t.Fatal(err)
	}
	if want := []Listener{{Port: 9222, PID: 500}}; !slices.Equal(listeners, want) {
		t.Errorf("listeners %+v, want %+v", listeners, want)
	}

	if empty, err := parseWindowsListeners(""); err != nil || len(empty) != 0 {
		t.Errorf("empty output: %+v, %v", empty, err)
	}
}

func TestFindChromiumPerSystem(t *testing.T) {
	exists := func(paths ...string) func(string) bool {
		return func(p string) bool { return slices.Contains(paths, p) }
	}
	none := func(string) (string, error) { return "", os.ErrNotExist }
	onPath := func(name string) func(string) (string, error) {
		return func(n string) (string, error) {
			if n == name {
				return "/usr/bin/" + n, nil
			}
			return "", os.ErrNotExist
		}
	}
	env := func(string) string { return `C:\Users\u\AppData\Local` }

	for name, tc := range map[string]struct {
		goos   string
		look   func(string) (string, error)
		exists func(string) bool
		want   string
	}{
		"linux chromium-browser": {"linux", onPath("chromium-browser"), exists(), "/usr/bin/chromium-browser"},
		"linux none":             {"linux", none, exists(), ""},
		"darwin app":             {"darwin", none, exists("/Applications/Chromium.app/Contents/MacOS/Chromium"), "/Applications/Chromium.app/Contents/MacOS/Chromium"},
		"windows local":          {"windows", none, exists(`C:\Users\u\AppData\Local\Chromium\Application\chrome.exe`), `C:\Users\u\AppData\Local\Chromium\Application\chrome.exe`},
	} {
		t.Run(name, func(t *testing.T) {
			if got := findChromium(tc.goos, tc.look, tc.exists, env); got != tc.want {
				t.Errorf("got %q, want %q", got, tc.want)
			}
		})
	}
}
