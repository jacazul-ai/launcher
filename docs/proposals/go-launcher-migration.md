# Go Launcher Migration: State

**Audience:** Contributors and agents working on the launcher.
**Design:** [`go-launcher.md`](go-launcher.md). **Plan:** `jacazul-launcher`
(#113). **Last updated:** 2026-10-04.

This page tracks where the move from the Bash launchers to the Go
`jacazul` binary stands. The design lives in the proposal; this page holds
only the state. Update a row whenever its task changes state.

## When the migration is closed

The migration is closed when every row of "Launcher" below is done. At
that point the cutoff runs: the Bash launchers, `testdata/parity`,
`internal/parity` and the `parity` target are removed, and `make test`
runs the Go suite. Everything under "After the migration" starts from
there.

## Launcher

| Step | State | Task |
|---|---|---|
| Contract: module path, layout, make targets | done | `bb059c89` |
| Scaffold: `go.mod`, `cmd/jacazul`, `internal/cli`, Makefile, CI | done | `c1570a30` |
| Parity matrix of the Bash launchers (DRY+DEBUG references) | done | `078476b0` |
| Bootstraps in Go: project, environment, language, persona, taskwarrior, claude, onboard | done | `454bc8a1` |
| `jacazul claude`, DRY parity with `scripts/jacazul-claude` | done | `454bc8a1` |
| `jacazul claude`, environment handed to claude compared with Bash (non-DRY) | done (`f263d47`) | `454bc8a1` |
| Go tests independent of generated skills (CI red since `b9bff96`) | done (`3fd3b25`); CI result not checked | `454bc8a1` |
| Runtime defaults: `--project`, `--home`, `--session`, `JACAZUL_SESSION`, session `global` | done (`7552256`), task open | `300d84ef` |
| `jacazul pi`, `gemini`, `copilot`, `opencode` | pending | `d6467d3e` |
| Legacy `jacazul-<harness>` names route to the Go binary | pending | `f47da6cb` |
| `docs/cli.md` and the Bash deprecation path | pending | `c9a8af02` |
| Environment, process and security validation | pending | `3dcc38d7` |
| `jacazul flow`: native `session list`, HANDOFF column | done (`fe5417a`, `98061b1`) | `c0e949ff` |
| `jacazul flow`: pass-through to `tw-flow` | superseded by the embedded engine (#144): every command but `session list` runs in `flow.Run` after the storage check (`99335ea`); the check before a launch is pending | `48a5e288` |
| Skills without `project_id` baked in | done (`7edb0ca`), task open | `37345109` |
| Orientation: the engine hub is the single source | done (`baf37e7`), task open | `8e5d2af9` |

## Deferred

| Item | Why | Task |
|---|---|---|
| Persisted configuration file (`project.json`) | a separate feature; the launcher must not depend on a configuration-file path until it exists | `0deb80e0` |

## After the migration

| Item | Task |
|---|---|
| Hatch in Go, embedded skills | `f8bb971b` |
| On-demand and user-defined personas | `2175b6f2` |
| Embedded workflow engine (`flow.Run`), Taskwarrior data migration | plan `jacazul-flow-embedding` |
| Repair a moved or renamed project (silo, cache, memory, remote, worktree links); manual checklist in [`per-project-taskwarrior.md`](../per-project-taskwarrior.md#renaming-or-moving-a-project) | `74c9cb07` |
