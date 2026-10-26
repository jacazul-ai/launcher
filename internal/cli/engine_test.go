package cli

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	_ "modernc.org/sqlite"
)

// These tests run the pinned engine itself, not a fake: what jacazul
// resolves must be what the engine opens and reports.

func TestPinnedEngineCreatesTheDefaultDatabase(t *testing.T) {
	l := setup(t)

	if code, _, stderr := run(t, "--project", "sandbox_x", "flow", "status"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	flowHome := filepath.Join(l.home, ".jacazul")
	if !exists(filepath.Join(flowHome, "projects", "sandbox_x", "flow.sqlite3")) {
		t.Error("no database at ~/.jacazul/projects/<project>/flow.sqlite3")
	}
	// The engine's own default sits under <home>/flow; jacazul replaces it.
	if exists(filepath.Join(flowHome, "flow")) {
		t.Error("the engine fell back to its own default path")
	}
}

func TestPinnedEngineHonorsTheDatabaseOverride(t *testing.T) {
	l := setup(t)
	override := filepath.Join(t.TempDir(), "elsewhere", "flow.sqlite3")
	t.Setenv("JACAZUL_FLOW_DATABASE_PATH", override)

	if code, _, stderr := run(t, "--project", "sandbox_x", "flow", "status"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if !exists(override) {
		t.Error("no database at JACAZUL_FLOW_DATABASE_PATH")
	}
	if exists(filepath.Join(l.home, ".jacazul", "projects")) {
		t.Error("a database was created at the default path as well")
	}
}

// The engine reports the runtime it received: the project and session
// jacazul resolved, flagged as injected rather than computed on its own.
func TestPinnedEngineReceivesProjectAndSession(t *testing.T) {
	for name, tc := range map[string]struct {
		args    []string
		project string
		session string
	}{
		"flags":    {[]string{"--project", "sandbox_x", "--session", "dddddddd"}, "sandbox_x", "dddddddd"},
		"defaults": {nil, "", "global"},
	} {
		t.Run(name, func(t *testing.T) {
			l := setup(t)
			project := tc.project
			if project == "" {
				project = filepath.Base(filepath.Dir(l.project)) + "_" + filepath.Base(l.project)
			}
			code, stdout, stderr := run(t, append(tc.args, "flow", "info")...)
			if code != 0 {
				t.Fatalf("exit %d, stderr %q", code, stderr)
			}
			database := filepath.Join(l.home, ".jacazul", "projects", project, "flow.sqlite3")
			for _, want := range []string{
				"project_id: " + project + "\n",
				"project_id_source: runtime\n",
				"session_id: " + tc.session + "\n",
				"session_id_source: runtime\n",
				"database_path: " + database + "\n",
			} {
				if !strings.Contains(stdout, want) {
					t.Errorf("info lacks %q:\n%s", want, stdout)
				}
			}
		})
	}
}

// A database a newer engine already upgraded is refused by the engine's
// schema guard; jacazul passes its ACTION: on untouched and leaves the
// database as it was.
func TestPinnedEngineRefusesANewerSchema(t *testing.T) {
	l := setup(t)
	if code, _, stderr := run(t, "--project", "sandbox_x", "flow", "status"); code != 0 {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	database := filepath.Join(l.home, ".jacazul", "projects", "sandbox_x", "flow.sqlite3")
	db, err := sql.Open("sqlite", database)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var supported int64
	if err := db.QueryRow("SELECT MAX(version_id) FROM goose_db_version").Scan(&supported); err != nil {
		t.Fatal(err)
	}
	newer := supported + 1
	if _, err := db.Exec("INSERT INTO goose_db_version (version_id, is_applied) VALUES (?, 1)", newer); err != nil {
		t.Fatal(err)
	}
	before, err := os.ReadFile(database)
	if err != nil {
		t.Fatal(err)
	}

	code, stdout, stderr := run(t, "--project", "sandbox_x", "flow", "status")
	if code == 0 {
		t.Fatalf("exit 0 on a newer schema, stdout %q", stdout)
	}
	guard := fmt.Sprintf("database schema version %d is newer than the %d this binary supports\n"+
		"ACTION: Upgrade jacazul", newer, supported)
	if !strings.Contains(stderr, guard) {
		t.Errorf("stderr %q, want the engine's guard %q", stderr, guard)
	}
	if strings.Contains(stderr, "jacazul flow:") {
		t.Errorf("stderr %q, the launcher wrapped the engine's guidance", stderr)
	}
	after, err := os.ReadFile(database)
	if err != nil {
		t.Fatal(err)
	}
	if string(after) != string(before) {
		t.Error("the refused database was modified")
	}
}
