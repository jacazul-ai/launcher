package cli

import (
	"encoding/json"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"testing"

	"github.com/jacazul-ai/launcher/internal/testutil"
)

// fakeClaude is what the test binary records when it runs as claude.
type fakeClaude struct {
	Args []string          `json:"args"`
	Env  map[string]string `json:"env"`
}

// TestMain lets the test binary stand in for the claude executable: with
// FAKE_CLAUDE_MARKER set it records its arguments and environment and
// exits with FAKE_CLAUDE_EXIT.
func TestMain(m *testing.M) {
	if marker := os.Getenv("FAKE_CLAUDE_MARKER"); marker != "" {
		rec := fakeClaude{Args: os.Args[1:], Env: map[string]string{}}
		for _, kv := range os.Environ() {
			k, v, _ := strings.Cut(kv, "=")
			rec.Env[k] = v
		}
		data, _ := json.Marshal(rec)
		if err := os.WriteFile(marker, data, 0o644); err != nil {
			os.Exit(100)
		}
		code, _ := strconv.Atoi(os.Getenv("FAKE_CLAUDE_EXIT"))
		os.Exit(code)
	}
	os.Exit(m.Run())
}

// sessionVars are inherited from a Jacazul session running the tests and
// would leak into the launcher under test.
var sessionVars = []string{
	"JACAZUL_HOME", "JACAZUL_SESSION", "JACAZUL_SESSION_ID", "JACAZUL_PROJECT",
	"JACAZUL_PERSONA", "JACAZUL_MODE",
	"JACAZUL_CHAT_LANG", "JACAZUL_DATA_LANG", "JACAZUL_HARNESS", "JACAZUL_MODEL",
	"JACAZUL_FOCUS_PLAN", "JACAZUL_FOCUS_TASK", "CLAUDE_CONFIG_DIR",
	"TASKRC", "TASKDATA", "DRY", "DEBUG", "CONTEXT_GIT_USER", "JACAZUL_ENV_INITIALIZED",
	"JACAZUL_FLOW_DATABASE_PATH", "JACAZUL_REAL_TASK",
}

type launch struct {
	home, project, root, marker string
}

// setup isolates HOME and the working directory, points the launcher at
// this checkout and installs the test binary as claude.
func setup(t *testing.T) launch {
	t.Helper()
	for _, k := range sessionVars {
		t.Setenv(k, "")
	}
	root := testutil.Checkout(t)
	l := launch{home: t.TempDir(), project: t.TempDir(), root: root}
	l.marker = filepath.Join(t.TempDir(), "claude.json")
	t.Setenv("HOME", l.home)
	t.Setenv("FAKE_CLAUDE_MARKER", l.marker)
	t.Setenv("FAKE_CLAUDE_EXIT", "0")
	t.Chdir(l.project)

	self, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	bin := filepath.Join(l.home, ".local", "bin")
	if err := os.MkdirAll(bin, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(self, filepath.Join(bin, "claude")); err != nil {
		t.Fatal(err)
	}

	saved := executable
	executable = func() (string, error) { return filepath.Join(root, "bin", "jacazul"), nil }
	t.Cleanup(func() { executable = saved })
	return l
}

func (l launch) recorded(t *testing.T) fakeClaude {
	t.Helper()
	data, err := os.ReadFile(l.marker)
	if err != nil {
		t.Fatalf("claude did not run: %v", err)
	}
	var rec fakeClaude
	if err := json.Unmarshal(data, &rec); err != nil {
		t.Fatal(err)
	}
	return rec
}

func TestClaudeRunsWithThePromptAndUntouchedArgs(t *testing.T) {
	l := setup(t)
	code, _, stderr := run(t, "--session", "abcd1234", "claude", "--resume", "--session", "other", "-p", "hi")
	if code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	rec := l.recorded(t)
	if len(rec.Args) < 2 || rec.Args[0] != "--append-system-prompt" {
		t.Fatalf("args %q lack the session prompt", rec.Args)
	}
	if !strings.Contains(rec.Args[1], "The anchored persona for this session is Jacazul") {
		t.Errorf("prompt is not the rendered onboard prompt:\n%s", rec.Args[1])
	}
	if want := []string{"--resume", "--session", "other", "-p", "hi"}; !slices.Equal(rec.Args[2:], want) {
		t.Errorf("harness args %q, want %q", rec.Args[2:], want)
	}

	id := filepath.Base(filepath.Dir(l.project)) + "_" + filepath.Base(l.project)
	jhome := filepath.Join(l.home, ".jacazul-ai")
	for k, want := range map[string]string{
		"PROJECT_ID":             id,
		"JACAZUL_PROJECT":        id,
		"JACAZUL_HOME":           jhome,
		"TASKDATA":               filepath.Join(jhome, ".task", id),
		"JACAZUL_SESSION":        "abcd1234",
		"JACAZUL_SESSION_ID":     "abcd1234",
		"JACAZUL_MODE":           "COUNSELOR",
		"JACAZUL_HARNESS":        "claude",
		"JACAZUL_PERSONA":        "jacazul",
		"JACAZUL_CHAT_LANG":      "pt-br",
		"JACAZUL_DATA_LANG":      "en",
		"JACAZUL_TASK_SIGNATURE": "— Jacazul (unspecified; harness: claude; session: abcd1234)",
		"CLAUDE_CONFIG_DIR":      filepath.Join(jhome, "agents", "claude"),
		"CONTEXT_REAL_PATH":      l.project,
		// Keeps a nested legacy Bash launcher from rerunning its bootstrap
		// and minting a session, until f47da6cb routes those names here.
		"JACAZUL_ENV_INITIALIZED": "true",
	} {
		if got := rec.Env[k]; got != want {
			t.Errorf("%s=%q, want %q", k, got, want)
		}
	}
	path := filepath.SplitList(rec.Env["PATH"])
	if len(path) < 3 || path[0] != filepath.Join(l.root, "scripts") || path[1] != filepath.Join(jhome, ".venv", "bin") {
		t.Errorf("PATH does not start with the wrapper and venv dirs: %q", rec.Env["PATH"])
	}
	if path[len(path)-1] != filepath.Join(l.root, "skills", "taskwarrior-expert", "scripts") {
		t.Errorf("PATH does not end with the workflow scripts: %q", rec.Env["PATH"])
	}
	if _, err := os.Lstat(filepath.Join(jhome, "agents", "claude", "skills", "jacazul-engine")); err != nil {
		t.Errorf("claude bootstrap did not link skills: %v", err)
	}
}

// Strong defaults: with no flag or variable the session is global, and
// JACAZUL_SESSION_ID stays unset so tw-flow keeps the global focus.json.
func TestClaudeDefaultsToTheGlobalSession(t *testing.T) {
	l := setup(t)
	if code, _, stderr := run(t, "claude"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	rec := l.recorded(t)
	if got := rec.Env["JACAZUL_SESSION"]; got != "global" {
		t.Errorf("JACAZUL_SESSION=%q, want global", got)
	}
	if got := rec.Env["JACAZUL_SESSION_ID"]; got != "" {
		t.Errorf("JACAZUL_SESSION_ID=%q, want it unset for the global session", got)
	}
	if got := rec.Env["JACAZUL_TASK_SIGNATURE"]; !strings.HasSuffix(got, "session: global)") {
		t.Errorf("JACAZUL_TASK_SIGNATURE=%q, want the global session", got)
	}
}

// --project and --home pin what tests and sandboxes need; the flag beats
// the variable, the variable beats the computed default.
func TestClaudeProjectAndHomePrecedence(t *testing.T) {
	for _, tc := range []struct {
		name        string
		args        []string
		vars        map[string]string
		wantProject string
		wantHome    string
	}{
		{"flags", []string{"--project", "sandbox_flag", "--home", "/flag-home"}, nil, "sandbox_flag", "/flag-home"},
		{"environment", nil, map[string]string{"JACAZUL_PROJECT": "sandbox_env", "JACAZUL_HOME": "/env-home"}, "sandbox_env", "/env-home"},
		{"flag beats environment", []string{"--project", "sandbox_flag", "--home", "/flag-home"},
			map[string]string{"JACAZUL_PROJECT": "sandbox_env", "JACAZUL_HOME": "/env-home"}, "sandbox_flag", "/flag-home"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			l := setup(t)
			// Homes are named relative to the test's HOME.
			for k, v := range tc.vars {
				if k == "JACAZUL_HOME" {
					v = filepath.Join(l.home, v)
				}
				t.Setenv(k, v)
			}
			args := slices.Clone(tc.args)
			for i, a := range args {
				if a == "--home" {
					args[i+1] = filepath.Join(l.home, args[i+1])
				}
			}
			if code, _, stderr := run(t, append(args, "claude")...); code != 0 {
				t.Fatalf("exit %d, stderr %q", code, stderr)
			}
			rec := l.recorded(t)
			home := filepath.Join(l.home, tc.wantHome)
			for k, want := range map[string]string{
				"PROJECT_ID":      tc.wantProject,
				"JACAZUL_PROJECT": tc.wantProject,
				"JACAZUL_HOME":    home,
				"TASKDATA":        filepath.Join(home, ".task", tc.wantProject),
			} {
				if got := rec.Env[k]; got != want {
					t.Errorf("%s=%q, want %q", k, got, want)
				}
			}
		})
	}
}

func TestClaudeReturnsTheHarnessExitCode(t *testing.T) {
	setup(t)
	t.Setenv("FAKE_CLAUDE_EXIT", "3")
	if code, _, stderr := run(t, "claude"); code != 3 {
		t.Fatalf("exit %d, want 3; stderr %q", code, stderr)
	}
}

func TestClaudeExitBannerNeedsAnIndependentSession(t *testing.T) {
	l := setup(t)
	_, stdout, _ := run(t, "--session", "abcd1234", "claude")
	if strings.Contains(stdout, "To resume") {
		t.Fatalf("banner without a session file:\n%s", stdout)
	}

	id := filepath.Base(filepath.Dir(l.project)) + "_" + filepath.Base(l.project)
	focus := filepath.Join(l.home, ".jacazul-ai", ".task", id, "focus-abcd1234.json")
	if err := os.WriteFile(focus, []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}
	_, stdout, _ = run(t, "--session", "abcd1234", "claude")
	if !strings.Contains(stdout, "To resume: jacazul --session abcd1234 claude") {
		t.Fatalf("no resume banner:\n%s", stdout)
	}
}

func TestClaudeDryRunStopsBeforeTheHarness(t *testing.T) {
	for name, args := range map[string][]string{
		"flag": {"--dry", "claude", "-p", "hi"},
		"env":  {"claude", "-p", "hi"},
	} {
		t.Run(name, func(t *testing.T) {
			l := setup(t)
			if name == "env" {
				t.Setenv("DRY", "true")
			}
			code, stdout, stderr := run(t, args...)
			if code != 0 {
				t.Fatalf("exit %d, stderr %q", code, stderr)
			}
			if _, err := os.Stat(l.marker); err == nil {
				t.Fatal("claude ran under --dry")
			}
			want := "✅ Dry run complete. Claude bootstrap verified for project [" +
				filepath.Base(filepath.Dir(l.project)) + "_" + filepath.Base(l.project) + "].\n" +
				"🐊 Arguments for claude: --append-system-prompt \"[ONBOARD_PROMPT]\" -p hi\n"
			if !strings.HasSuffix(stdout, want) {
				t.Errorf("stdout:\n%s\nwant suffix:\n%s", stdout, want)
			}
			if strings.Contains(stdout, "Starting for project") {
				t.Errorf("debug line without --debug:\n%s", stdout)
			}
		})
	}
}

func TestClaudeWithoutACheckoutStopsWithAnInstruction(t *testing.T) {
	l := setup(t)
	elsewhere := filepath.Join(t.TempDir(), "go", "bin", "jacazul")
	executable = func() (string, error) { return elsewhere, nil }
	code, _, stderr := run(t, "claude")
	if code != 1 {
		t.Fatalf("exit %d, want 1", code)
	}
	if !strings.Contains(stderr, filepath.Dir(filepath.Dir(elsewhere))) || !strings.Contains(stderr, "make build") {
		t.Errorf("stderr does not explain the missing checkout: %q", stderr)
	}
	if _, err := os.Stat(l.marker); err == nil {
		t.Fatal("claude ran without a checkout")
	}
}

func TestClaudeNotInstalledFails(t *testing.T) {
	l := setup(t)
	if err := os.Remove(filepath.Join(l.home, ".local", "bin", "claude")); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", t.TempDir())
	code, _, stderr := run(t, "claude")
	if code != 1 || !strings.Contains(stderr, "claude command not found") {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
}

func TestClaudeKeepsTheLegacySessionFlag(t *testing.T) {
	l := setup(t)
	if code, _, stderr := run(t, "--jacazul-session", "abcd1234", "claude"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if got := l.recorded(t).Env["JACAZUL_SESSION_ID"]; got != "abcd1234" {
		t.Errorf("JACAZUL_SESSION_ID=%q, want abcd1234", got)
	}
	if _, stdout, _ := run(t, "--help"); strings.Contains(stdout, "jacazul-session") {
		t.Errorf("help lists the legacy flag:\n%s", stdout)
	}
}
