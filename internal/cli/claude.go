package cli

import (
	"cmp"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"os/user"
	"path/filepath"
	"strings"

	"github.com/jacazul-ai/flow"
	"github.com/jacazul-ai/launcher/internal/bootstrap/claude"
	"github.com/jacazul-ai/launcher/internal/bootstrap/environment"
	"github.com/jacazul-ai/launcher/internal/bootstrap/language"
	"github.com/jacazul-ai/launcher/internal/bootstrap/onboard"
	"github.com/jacazul-ai/launcher/internal/bootstrap/persona"
	"github.com/jacazul-ai/launcher/internal/bootstrap/project"
	"github.com/jacazul-ai/launcher/internal/bootstrap/taskwarrior"
	claudetmpl "github.com/jacazul-ai/launcher/templates/claude"
	tasktmpl "github.com/jacazul-ai/launcher/templates/taskwarrior"
)

// executable locates the running binary; tests point it at a checkout.
var executable = os.Executable

// runClaude prepares the Jacazul environment and runs Claude Code with
// the session prompt, mirroring scripts/jacazul-claude. args pass to
// claude untouched.
func runClaude(opts Options, args []string, stdout, stderr io.Writer) int {
	debug := opts.Debug || os.Getenv("DEBUG") != ""
	dry := opts.Dry || os.Getenv("DRY") != ""
	fail := func(err error) int {
		fmt.Fprintf(stderr, "❌ jacazul claude: %v\n", err)
		return 1
	}

	root, err := checkout()
	if err != nil {
		return fail(err)
	}
	cwd, err := os.Getwd()
	if err != nil {
		return fail(err)
	}
	id, err := resolveProject(opts.Project, cwd)
	if err != nil {
		return fail(err)
	}
	env := environment.Resolve(environment.Input{
		Getenv:      os.Getenv,
		ProjectID:   id.ID,
		HomeFlag:    opts.Home,
		SessionFlag: cmp.Or(opts.Session, opts.LegacySession),
		SkipDirs:    []string{filepath.Join(root, "scripts")},
	})
	anchored, err := project.AnchoredPersona(env.Home, id.ID)
	if err != nil {
		return fail(err)
	}
	lang := language.Resolve(os.Getenv, language.Pair{}, filepath.Join(env.Home, "language.json"))
	if debug {
		fmt.Fprintf(stdout, "🌐 Jacazul Language: Chat=%s | Data=%s\n", lang.Chat, lang.Data)
	}

	// The venv is prepared by scripts/configure, not on every launch.
	venv := filepath.Join(env.Home, ".venv")
	if !isExecutable(filepath.Join(venv, "bin", "tw-flow")) &&
		!isExecutable(filepath.Join(root, "skills", "taskwarrior-expert", "scripts", "tw-flow")) {
		fmt.Fprintln(stderr, "❌ CRITICAL ERROR: tw-flow not found or not executable.")
		fmt.Fprintln(stderr, "   The workspace structure might be corrupted. Please run 'scripts/configure' to fix it.")
		return 1
	}

	tw, err := taskwarrior.Bootstrap(taskwarrior.Input{
		ProjectID:   id.ID,
		Home:        env.Home,
		Mode:        env.Mode,
		TaskRC:      os.Getenv("TASKRC"),
		SessionID:   sessionFor(env.SessionID),
		FocusPlan:   os.Getenv("JACAZUL_FOCUS_PLAN"),
		FocusTask:   os.Getenv("JACAZUL_FOCUS_TASK"),
		RealTask:    env.RealTask,
		TaskVersion: env.TaskVersion,
		Debug:       debug,
		Templates:   taskwarrior.Templates{Caged: tasktmpl.Caged, Unhinged: tasktmpl.Unhinged},
		Out:         stdout,
	})
	if err != nil {
		return fail(err)
	}
	if debug {
		fmt.Fprintf(stdout, "🐊 Jacazul Runtime Initialized | Mode: %s | Binary: %s\n", env.Mode, cmp.Or(env.RealTask, "not found"))
	}

	harness := cmp.Or(os.Getenv("JACAZUL_HARNESS"), "claude")
	p := persona.Resolve(persona.Input{
		Getenv:    os.Getenv,
		Project:   anchored,
		Harness:   harness,
		SessionID: env.SessionID,
	})
	if p.Invalid && debug {
		fmt.Fprintln(stderr, "⚠️ Invalid anchored persona; using Jacazul.")
	}

	configDir := claude.ConfigDir(os.Getenv("CLAUDE_CONFIG_DIR"), env.Home)
	err = claude.Bootstrap(claude.Input{
		ConfigDir: configDir,
		Root:      root,
		Template:  claudetmpl.Settings,
		Debug:     debug,
		Out:       stdout,
	})
	if err != nil {
		return fail(err)
	}

	prompt, err := onboard.Prompt(p.ID, onboard.Vars{
		PersonaDisplay:    p.Display,
		PersonaSignature:  p.Signature,
		ResponseSignature: p.ResponseSignature,
		TaskSignature:     p.TaskSignature,
		Mode:              env.Mode,
		ChatLang:          lang.Chat,
		DataLang:          lang.Data,
	})
	if err != nil {
		return fail(err)
	}

	path := strings.Join([]string{
		filepath.Join(root, "scripts"),
		filepath.Join(venv, "bin"),
		os.Getenv("PATH"),
		filepath.Join(root, "skills", "taskwarrior-expert", "scripts"),
	}, string(filepath.ListSeparator))
	bin := claudeBinary(os.Getenv("HOME"), path)
	if bin == "" {
		fmt.Fprintln(stderr, "❌ claude command not found in PATH or ~/.local/bin/.")
		return 1
	}

	// The harness always opens with a flow database: opening settles it
	// first, the same way jacazul flow does, and asks before it migrates
	// the Taskwarrior silo. A dry run keeps the Bash launcher's output;
	// jacazul --dry flow status shows what opening would do.
	if !dry {
		fenv, silo := flowEnv(opts, id.ID)
		ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
		opened := openStorage(ctx, root, silo, fenv, flow.Streams{Stdin: os.Stdin, Stdout: stdout, Stderr: stderr}, false, opts.Verbose)
		stop()
		if opened != 0 {
			return opened
		}
	}

	if debug {
		fmt.Fprintf(stdout, "🐊 jacazul-claude: Starting for project [%s]\n", id.ID)
	}
	if dry {
		fmt.Fprintf(stdout, "✅ Dry run complete. Claude bootstrap verified for project [%s].\n", id.ID)
		fmt.Fprintf(stdout, "🐊 Arguments for claude: --append-system-prompt \"[ONBOARD_PROMPT]\" %s\n", strings.Join(args, " "))
		return 0
	}

	vars := [][2]string{
		{"JACAZUL_PROJECT", id.ID},
		{"JACAZUL_HOME", env.Home},
		{"JACAZUL_SESSION", env.SessionID},
		// tw-flow's names until its cutoff.
		{"PROJECT_ID", id.ID},
		{"TASKDATA", tw.TaskData},
		{"JACAZUL_MODE", env.Mode},
		{"JACAZUL_REAL_TASK", env.RealTask},
		{"JACAZUL_TASK_VERSION", env.TaskVersion},
		{"JACAZUL_CHAT_LANG", lang.Chat},
		{"JACAZUL_DATA_LANG", lang.Data},
		{"JACAZUL_HARNESS", harness},
		{"JACAZUL_PERSONA", p.ID},
		{"JACAZUL_PERSONA_DISPLAY", p.Display},
		{"JACAZUL_PERSONA_NAME", p.Name},
		{"JACAZUL_PERSONA_SIGNATURE", p.Signature},
		{"JACAZUL_MODEL", p.Model},
		{"JACAZUL_SESSION_SHORT", p.SessionShort},
		{"JACAZUL_RESPONSE_SIGNATURE", p.ResponseSignature},
		{"JACAZUL_TASK_SIGNATURE", p.TaskSignature},
		{"CONTEXT_REAL_PATH", cwd},
		{"CONTEXT_SYSTEM_USER", username()},
		{"CONTEXT_GIT_USER", cmp.Or(os.Getenv("CONTEXT_GIT_USER"), username())},
		{"CLAUDE_CONFIG_DIR", configDir},
		{"PATH", path},
		// The run-once guard of scripts/bootstrap/environment. A legacy Bash
		// launcher started inside the harness would otherwise rerun its whole
		// bootstrap and mint its own session. Transitional: it goes when
		// f47da6cb routes the legacy names through this binary.
		{"JACAZUL_ENV_INITIALIZED", "true"},
	}
	// tw-flow reads JACAZUL_SESSION_ID as an independent session; the global
	// session leaves it unset so tw-flow keeps the global focus.json.
	if sid := sessionFor(env.SessionID); sid != "" {
		vars = append(vars, [2]string{"JACAZUL_SESSION_ID", sid})
	}
	if tw.TaskRC != "" {
		vars = append(vars, [2]string{"TASKRC", tw.TaskRC})
	}
	if isDir(venv) {
		vars = append(vars, [2]string{"VIRTUAL_ENV", venv})
	}
	if debug {
		vars = append(vars, [2]string{"DEBUG", "true"})
	}

	cmd := exec.Command(bin, append([]string{"--append-system-prompt", prompt}, args...)...)
	cmd.Env = withVars(os.Environ(), vars)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, stdout, stderr
	// Ctrl-C belongs to claude; the launcher stays alive for the banner.
	signal.Ignore(os.Interrupt)
	defer signal.Reset(os.Interrupt)
	code := 0
	if err := cmd.Run(); err != nil {
		var exit *exec.ExitError
		if !errors.As(err, &exit) {
			return fail(err)
		}
		code = exit.ExitCode()
	}

	if sid := sessionFor(env.SessionID); sid != "" && isFile(filepath.Join(tw.TaskData, "focus-"+sid+".json")) {
		fmt.Fprintln(stdout)
		fmt.Fprintln(stdout, "╭─ 🐊 Jacazul Session ───────────────────────────────────────╮")
		fmt.Fprintf(stdout, "│  To resume: jacazul --session %s claude\n", env.SessionID)
		fmt.Fprintln(stdout, "╰────────────────────────────────────────────────────────────╯")
	}
	return code
}

// checkout is the repository the binary was built in: bin/jacazul's
// parent. Temporary: it goes away once the skills and extensions are
// embedded in the binary.
func checkout() (string, error) {
	if root := os.Getenv("JACAZUL_ROOT"); root != "" {
		if !isDir(filepath.Join(root, "skills")) {
			return "", fmt.Errorf("JACAZUL_ROOT=%s has no skills/; point it at a launcher checkout or unset it", root)
		}
		return root, nil
	}
	exe, err := executable()
	if err != nil {
		return "", err
	}
	if real, err := filepath.EvalSymlinks(exe); err == nil {
		exe = real
	}
	root := filepath.Dir(filepath.Dir(exe))
	if isDir(filepath.Join(root, "skills")) {
		return root, nil
	}
	// go run builds the binary in the Go build cache: look for this module
	// from the working directory instead.
	if cwd, err := os.Getwd(); err == nil {
		for dir := cwd; ; dir = filepath.Dir(dir) {
			if isDir(filepath.Join(dir, "skills")) && isLauncherModule(filepath.Join(dir, "go.mod")) {
				return dir, nil
			}
			if dir == filepath.Dir(dir) {
				break
			}
		}
	}
	return "", fmt.Errorf("no launcher checkout around %s (%s has no skills/); "+
		"until skills are embedded in the binary, run 'make build' in a checkout "+
		"and launch its bin/jacazul or a link to it, or go run ./cmd/jacazul from the checkout", exe, root)
}

// isLauncherModule reports whether the go.mod at path declares this module.
func isLauncherModule(path string) bool {
	data, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	first, _, _ := strings.Cut(string(data), "\n")
	return strings.TrimSpace(first) == "module github.com/jacazul-ai/launcher"
}

// claudeBinary prefers the native installer's ~/.local/bin/claude, then
// the first claude on path.
func claudeBinary(home, path string) string {
	if bin := filepath.Join(home, ".local", "bin", "claude"); isExecutable(bin) {
		return bin
	}
	for _, dir := range filepath.SplitList(path) {
		if bin := filepath.Join(dir, "claude"); dir != "" && isExecutable(bin) {
			return bin
		}
	}
	return ""
}

// withVars returns environ with each var set, replacing inherited values.
func withVars(environ []string, vars [][2]string) []string {
	set := map[string]bool{}
	for _, v := range vars {
		set[v[0]] = true
	}
	out := make([]string, 0, len(environ)+len(vars))
	for _, kv := range environ {
		if k, _, _ := strings.Cut(kv, "="); !set[k] {
			out = append(out, kv)
		}
	}
	for _, v := range vars {
		out = append(out, v[0]+"="+v[1])
	}
	return out
}

func username() string {
	if u, err := user.Current(); err == nil {
		return u.Username
	}
	return os.Getenv("USER")
}

func isDir(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

func isFile(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.Mode().IsRegular()
}

func isExecutable(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir() && info.Mode()&0o111 != 0
}
