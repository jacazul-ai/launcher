package ui

import (
	"bufio"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// The parsers live here without build tags, so every system's format is
// tested on every system; the collect_* files only run the commands.

// clockTick is USER_HZ, the unit of /proc/<pid>/stat start times. The
// kernel exports 100 on every mainstream architecture, and reading it
// through sysconf would need cgo.
const clockTick = 10 * time.Millisecond

// readProc reads processes and TCP listeners from a Linux /proc tree at
// root. Processes or sockets the current user cannot read are skipped.
func readProc(root string) (Snapshot, error) {
	uptime, err := readUptime(filepath.Join(root, "uptime"))
	if err != nil {
		return Snapshot{}, err
	}
	entries, err := os.ReadDir(root)
	if err != nil {
		return Snapshot{}, err
	}

	var s Snapshot
	owners := map[string]int{} // socket inode -> pid
	for _, e := range entries {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		dir := filepath.Join(root, e.Name())
		cmdline, err := os.ReadFile(filepath.Join(dir, "cmdline"))
		if err != nil || len(cmdline) == 0 {
			continue
		}
		stat, err := os.ReadFile(filepath.Join(dir, "stat"))
		if err != nil {
			continue
		}
		ppid, start, ok := parseStat(string(stat))
		if !ok {
			continue
		}
		command := strings.Join(strings.FieldsFunc(string(cmdline), func(r rune) bool { return r == 0 }), " ")
		s.Processes = append(s.Processes, Process{PID: pid, PPID: ppid, Age: uptime - start, Command: command})

		fds, _ := os.ReadDir(filepath.Join(dir, "fd"))
		for _, fd := range fds {
			target, err := os.Readlink(filepath.Join(dir, "fd", fd.Name()))
			if inode, ok := strings.CutPrefix(target, "socket:["); err == nil && ok {
				owners[strings.TrimSuffix(inode, "]")] = pid
			}
		}
	}

	for _, name := range []string{"tcp", "tcp6"} {
		data, err := os.ReadFile(filepath.Join(root, "net", name))
		if err != nil {
			continue
		}
		for line := range strings.Lines(string(data)) {
			f := strings.Fields(line)
			if len(f) < 10 || f[3] != "0A" { // 0A is TCP_LISTEN
				continue
			}
			_, hexPort, _ := strings.Cut(f[1], ":")
			port, err := strconv.ParseInt(hexPort, 16, 32)
			if err != nil {
				continue
			}
			s.Listeners = append(s.Listeners, Listener{Port: int(port), PID: owners[f[9]]})
		}
	}
	return s, nil
}

func readUptime(path string) (time.Duration, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, err
	}
	first, _, _ := strings.Cut(string(data), " ")
	seconds, err := strconv.ParseFloat(first, 64)
	if err != nil {
		return 0, err
	}
	return time.Duration(seconds * float64(time.Second)), nil
}

// parseStat reads the parent PID and start time from /proc/<pid>/stat. The
// command name may hold spaces and parentheses, so fields count from the
// last ')'.
func parseStat(stat string) (ppid int, start time.Duration, ok bool) {
	i := strings.LastIndexByte(stat, ')')
	if i < 0 {
		return 0, 0, false
	}
	f := strings.Fields(stat[i+1:])
	if len(f) < 20 {
		return 0, 0, false
	}
	ppid, err := strconv.Atoi(f[1])
	if err != nil {
		return 0, 0, false
	}
	ticks, err := strconv.ParseInt(f[19], 10, 64)
	if err != nil {
		return 0, 0, false
	}
	return ppid, time.Duration(ticks) * clockTick, true
}

// parsePS reads `ps -axo pid=,ppid=,etime=,command=`, the form both procps
// and the BSD ps accept. Lines that do not parse are skipped.
func parsePS(out string) []Process {
	var procs []Process
	for line := range strings.Lines(out) {
		f := strings.Fields(line)
		if len(f) < 4 {
			continue
		}
		pid, err1 := strconv.Atoi(f[0])
		ppid, err2 := strconv.Atoi(f[1])
		age, ok := parseElapsed(f[2])
		if err1 != nil || err2 != nil || !ok {
			continue
		}
		procs = append(procs, Process{PID: pid, PPID: ppid, Age: age, Command: strings.Join(f[3:], " ")})
	}
	return procs
}

// parseElapsed reads ps's [[dd-]hh:]mm:ss.
func parseElapsed(s string) (time.Duration, bool) {
	var days int
	if d, rest, found := strings.Cut(s, "-"); found {
		n, err := strconv.Atoi(d)
		if err != nil {
			return 0, false
		}
		days, s = n, rest
	}
	parts := strings.Split(s, ":")
	if len(parts) < 2 || len(parts) > 3 {
		return 0, false
	}
	var total time.Duration
	for _, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil {
			return 0, false
		}
		total = total*60 + time.Duration(n)
	}
	return total*time.Second + time.Duration(days)*24*time.Hour, true
}

// parseLsof reads `lsof -nP -iTCP -sTCP:LISTEN -Fpn`: a p line opens a
// process, each n line is one of its sockets.
func parseLsof(out string) []Listener {
	var listeners []Listener
	seen := map[Listener]bool{}
	pid := 0
	sc := bufio.NewScanner(strings.NewReader(out))
	for sc.Scan() {
		line := sc.Text()
		if line == "" {
			continue
		}
		switch line[0] {
		case 'p':
			pid, _ = strconv.Atoi(line[1:])
		case 'n':
			i := strings.LastIndexByte(line, ':')
			port, err := strconv.Atoi(line[i+1:])
			if i < 0 || err != nil {
				continue
			}
			l := Listener{Port: port, PID: pid}
			if !seen[l] {
				seen[l] = true
				listeners = append(listeners, l)
			}
		}
	}
	return listeners
}

// parseWindowsProcesses reads the JSON of Get-CimInstance Win32_Process
// with an Age column in seconds. Processes without a visible command line
// (system processes, other users' without elevation) stay in with an empty
// command, so they still count as live parents.
func parseWindowsProcesses(out string) ([]Process, error) {
	var rows []struct {
		ProcessId       int
		ParentProcessId int
		CommandLine     *string
		Age             int64
	}
	if err := decodeRows(out, &rows); err != nil {
		return nil, err
	}
	procs := make([]Process, 0, len(rows))
	for _, r := range rows {
		var command string
		if r.CommandLine != nil {
			command = *r.CommandLine
		}
		procs = append(procs, Process{
			PID: r.ProcessId, PPID: r.ParentProcessId,
			Age: time.Duration(r.Age) * time.Second, Command: command,
		})
	}
	return procs, nil
}

// parseWindowsListeners reads the JSON of Get-NetTCPConnection -State Listen.
func parseWindowsListeners(out string) ([]Listener, error) {
	var rows []struct {
		LocalPort     int
		OwningProcess int
	}
	if err := decodeRows(out, &rows); err != nil {
		return nil, err
	}
	listeners := make([]Listener, 0, len(rows))
	for _, r := range rows {
		listeners = append(listeners, Listener{Port: r.LocalPort, PID: r.OwningProcess})
	}
	return listeners, nil
}

// decodeRows decodes ConvertTo-Json output, which is an array for several
// rows, a bare object for one and nothing at all for none.
func decodeRows[T any](out string, rows *[]T) error {
	out = strings.TrimSpace(out)
	switch {
	case out == "":
		return nil
	case strings.HasPrefix(out, "{"):
		var one T
		if err := json.Unmarshal([]byte(out), &one); err != nil {
			return err
		}
		*rows = []T{one}
		return nil
	case strings.HasPrefix(out, "["):
		return json.Unmarshal([]byte(out), rows)
	}
	return errors.New("unexpected PowerShell output: " + firstLine(out))
}

func firstLine(s string) string {
	line, _, _ := strings.Cut(s, "\n")
	return line
}

// findChromium looks for a Chromium installed for automation: on PATH under
// its own names, then at the system's usual install locations. The daily
// browsers (Chrome, Edge, Brave) are never candidates.
func findChromium(goos string, lookPath func(string) (string, error), exists func(string) bool, getenv func(string) string) string {
	var names, paths []string
	switch goos {
	case "darwin":
		names = []string{"chromium"}
		paths = []string{"/Applications/Chromium.app/Contents/MacOS/Chromium"}
	case "windows":
		names = []string{"chromium.exe"}
		for _, base := range []string{getenv("LOCALAPPDATA"), getenv("ProgramFiles")} {
			if base != "" {
				paths = append(paths, base+`\Chromium\Application\chrome.exe`)
			}
		}
	default:
		names = []string{"chromium", "chromium-browser"}
		paths = []string{"/usr/bin/chromium", "/usr/bin/chromium-browser", "/snap/bin/chromium"}
	}
	for _, n := range names {
		if p, err := lookPath(n); err == nil {
			return p
		}
	}
	for _, p := range paths {
		if exists(p) {
			return p
		}
	}
	return ""
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
