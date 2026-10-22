# Proposal: The Go Launcher

**Status:** In progress. `jacazul claude` is implemented and held to the
claude parity references; the other harness subcommands are not
implemented yet.
**Audience:** Contributors and agents working on the launcher.
**Related:** #113, plan `jacazul-launcher`, `go-expert`, `bash-expert`,
[`tw-flow-session.md`](../tw-flow-session.md). Step-by-step state:
[`go-launcher-migration.md`](go-launcher-migration.md).

## What changes for the user

One Go binary, `jacazul`, replaces the per-harness Bash launchers. Each
harness becomes a subcommand:

| Today | With the Go launcher |
|---|---|
| `jacazul-claude` | `jacazul claude` |
| `jacazul-pi` | `jacazul pi` |
| `jacazul-gemini` | `jacazul gemini` |
| `jacazul-copilot` | `jacazul copilot` |
| `jacazul-opencode` | `jacazul opencode` |

The old names keep working during the transition as entry points to the
same binary. `jacazul-gemini-sandboxed` is not ported (see Out of scope).

## Command shape

```text
jacazul [--dry] [--debug] [--project <id>] [--home <dir>] [--session <id>]
        <harness> [harness args...]
```

`--project`, `--home` and `--session` follow the runtime defaults below.

Workflow commands never go through a harness. Everything that belongs to
the workflow lives under `jacazul flow`, with the same `jacazul` options in
front:

```text
jacazul [--project <id>] [--home <dir>] [--session <id>] flow <command> [args...]
```

Listing sessions is `jacazul flow session list`, not `jacazul pi ...`: no
harness starts for it. A harness subcommand only launches its harness.

- Everything before the harness name belongs to `jacazul`; everything after
  it reaches the harness untouched. The Bash launchers scanned every
  argument for `--jacazul-session` and `--resume`; the Go launcher
  intercepts nothing after the harness.
- `--session` selects the Jacazul session, the focus lane that carries
  mission continuity. Its position tells it apart from the harness's own
  session flags for conversation continuity (see
  [`tw-flow-session.md`](../tw-flow-session.md)): `jacazul --session X pi
  --session Y` gives X to Jacazul and Y to pi. `--jacazul-session` is a
  hidden alias until the cutoff.
- `--dry` runs every bootstrap step except the harness launch; `--debug`
  prints what each step does. The `DRY` and `DEBUG` environment variables
  stay honored for compatibility; either source turns the mode on.
- `-v`/`--version` prints the version stamped by the Go toolchain from
  version control (a tag, or a pseudo-version with `+dirty`).

### `--resume` is fixed on the way

Since the Bash launchers were introduced, `jacazul-<harness> --resume`
skips the onboard prompt and drops `--resume` before calling the harness,
so the conversation is never resumed. With the pass-through above,
`--resume` reaches the harness. Until the open decision below settles
whether a resumed conversation skips the onboard prompt, `jacazul claude`
passes it on every launch. It changes nothing on a resume: Claude Code
records the system prompt, `--append-system-prompt` included, on the
conversation's first request and resends that record on every resume
(`--system-prompt-snapshot`, on by default), so the resumed conversation
keeps the persona and the session signature it started with. Resuming with
another `--session` therefore mixes two Jacazul session IDs; tying the
harness conversation to the Jacazul session is an open decision.

## Runtime defaults

The launcher and the workflow engine share one set of defaults. The
configuration file is deferred.

**Strong defaults.** The computed defaults must be right on their own: a
plain `jacazul <harness>` run from any project directory, worktree
included, resolves the correct project, home and session without a flag or
variable. Flags and variables are overrides for special cases, not part of
normal use. `--project` (and `JACAZUL_PROJECT`) exists mainly for our
tests and for defining sandboxes, where the project must be pinned instead
of resolved from the working directory.

Precedence: explicit CLI parameter > environment variable > configuration
file > computed default.

| Value | Flag | Environment | Computed default |
|---|---|---|---|
| Project | `--project` | `JACAZUL_PROJECT` | canonical project resolution |
| Home | `--home` | `JACAZUL_HOME` | `$HOME/.jacazul-ai` |
| Session | `--session` | `JACAZUL_SESSION` | `global` |

Canonical project resolution:

- A directory outside Git: the canonical `pwd` is the anchor.
- A normal Git repository: `git rev-parse --show-toplevel`.
- A linked worktree: the parent of `git-common-dir` when it ends in `.git`
  or `.bare`.
- Identity: `basename(parent(anchor)) + "_" + basename(anchor)`, so
  `flow/master` resolves to `jacazul-ai_flow`, never `jacazul-ai_master`.

Downstream, `jacazul` resolves the three values once and hands the same
values on. It exports them to the harness as `JACAZUL_PROJECT`,
`JACAZUL_HOME` and `JACAZUL_SESSION`, and passes them to the embedded engine
as `flow.Env`. The launcher owns the session: it preserves `JACAZUL_SESSION`
when one is provided, and the engine never generates a session ID per
process. Until the `tw-flow` cutoff, `PROJECT_ID` and `TASKDATA` stay
exported for `tw-flow`.

The persisted configuration file is a separate feature and is not
implemented. The launcher does not depend on, or invent, a
configuration-file path.

Implemented in `internal/bootstrap/environment` (`Home`, `Session`) and
`internal/cli` (`resolveProject`), shared by the harness subcommands and
`jacazul flow`:

- `--project` pins the project ID only. The anchor still comes from the
  working directory.
- Until the `tw-flow` cutoff, `JACAZUL_SESSION_ID` is read after
  `JACAZUL_SESSION`. It is exported only for a session that is not
  `global`, because `tw-flow` treats any value as an independent lane
  (`focus-<id>.json`).
- The global session gives the Taskwarrior bootstrap no session, so it
  seeds no lane and prints no `Session ID` line.
- The persona comes from the legacy `.task/<PROJECT_ID>/persona.json` that
  `jacazul-persona` writes. `project.json` is not read.

## Layout

The layout follows other Go projects of the organization:

```text
cmd/jacazul/main.go      the entry point only
internal/cli/            parser and commands, one file per harness
internal/bootstrap/      one package per bootstrap step
internal/parity/         temporary, test-only (see Parity below)
testdata/parity/         scenario table, capture script, references
```

The Go tree mirrors the Bash one, so each step has a counterpart that is
easy to trace and to hold to parity. Shared and harness-specific steps sit
side by side, as they do in `scripts/bootstrap/`:

| Bash | Go |
|---|---|
| `scripts/jacazul-<harness>` | `internal/cli/<harness>.go` |
| `scripts/bootstrap/<harness>` | `internal/bootstrap/<harness>/` |
| `scripts/bootstrap/project-identity` | `internal/bootstrap/project/` |
| `scripts/bootstrap/environment` | `internal/bootstrap/environment/` |
| `scripts/bootstrap/persona` | `internal/bootstrap/persona/` |
| `scripts/bootstrap/language` | `internal/bootstrap/language/` |
| `scripts/bootstrap/taskwarrior` | `internal/bootstrap/taskwarrior/` |
| `scripts/bootstrap/onboard` | `internal/bootstrap/onboard/` |
| `scripts/bootstrap/python` | removed: no Python on the launch path |
| `scripts/bootstrap/hatch` | the Go hatch (below) |

Shared steps are ported once and reused by every harness command.

- Module `github.com/jacazul-ai/launcher`, the repository's name since the
  rename from `jacazul-ai/jacazul-ai-cli` (#133).
- `go 1.25`, `jessevdk/go-flags`.
- Make targets: `build` (to `bin/jacazul`), `clean`, `fmt`, `go-test`,
  `tidy`, `vet`, `parity`. Until the Python cutoff `make test` stays the
  Python suite and the Go suite runs with `make go-test`; at the cutoff
  `make test` becomes the Go suite.
- CI: `.github/workflows/run_tests.yml` runs `make vet` and `make go-test`
  on Go 1.25 to 1.27 with read-only permissions.

## What moves into Go

The launcher runs no Python. Every step the Bash launchers source or spawn
is ported:

| Step | Today | In Go |
|---|---|---|
| Project identity, `PROJECT_ID` | `bootstrap/project-identity` | computed from the path |
| `JACAZUL_HOME` | forced to `~/.jacazul-ai` in two bootstraps | `--home`, then a preset value, then `~/.jacazul-ai` (Runtime defaults) |
| Session ID | `python3 -c uuid` | `--session`, then `JACAZUL_SESSION`, then `global`; never generated per launch (Runtime defaults) |
| Persona, language | `persona.json`, `language.json`, `jq`/`grep` | read in Go from the same files; `project.json` is deferred (below) |
| Mode | `JACAZUL_MODE`, default `COUNSELOR` | unchanged: a variable of the running session |
| Taskwarrior data and UDAs | `bootstrap/taskwarrior` | ported one to one, known issues included; transitional until the flow cutoff |
| Python venv | `uv venv` + `uv pip install -e` on every launch | off the launch path |
| Claude settings, skill and extension links | `bootstrap/claude` | merged and linked in Go, honoring `HOSTS`; links point into the checkout until the hatch embeds them (below) |
| Session prompt | `bootstrap/onboard` | rendered from the embedded `prompts/onboard.md` plus the active voice, without `eval` |
| Hatch | `jacazul-hatch` (Python) on every launch | the Go hatch, only when content changed (below) |

A Bash `DRY` launch takes about 1.1 s; `uv pip install -e` alone is about
590 ms of it, `jacazul-hatch` about 140 ms and `python3` for the session ID
about 33 ms.

## Per-project configuration (deferred)

**Deferred.** The persisted configuration file is a separate feature and
is not implemented. Until it lands, the launcher reads no `project.json`
(task `300d84ef` takes it off the launch path; `0deb80e0` waits for the
feature). In the precedence chain, the file sits between the environment
variable and the computed default. The design below is kept for that
feature.

Stable project settings move from environment variables to one file:

```json
// <JACAZUL_HOME>/projects/<PROJECT_ID>/project.json
{ "persona": "arnalbam", "language": { "chat": "pt-br", "data": "en" } }
```

- It absorbs `.task/<PROJECT_ID>/persona.json` and lets a project override
  the global `language.json`.
- Precedence: environment variable, then `project.json`, then the global
  `language.json`, then defaults.
- The file is the source; environment variables stay the transport to the
  harness and the tools it starts.
- Mode is not stored: it describes the running session.
- Migration reads `persona.json` when `project.json` is absent, and
  `jacazul-persona` writes the new file.

## The hatch

The hatch moves to Go and hatches everything hatchable, including skills
owned by other Go projects such as `jacazul-ai/flow`:

- Each provider module exports its hatchable files with `//go:embed`, for
  example `var Hatch embed.FS` over a `hatch/` directory that holds
  `skills/<name>/...`. This repository's own skills become a provider too.
- The launcher imports its providers through `go.mod`, so a skill's version
  is pinned to the version of the module that owns it.
- The hatch writes the files under `JACAZUL_HOME/agents/<harness>/skills/`,
  honoring `HOSTS`. Embedded content cannot be symlinked, so it writes
  copies with a version marker and re-hatches only when the binary's
  content differs, which takes the hatch off the per-launch path.
- Templates render with pongo2, which uses Django template syntax. Today's
  templates are Tornado's: `include` and `{{ variable }}` read the same, and
  Tornado's generic `{% end %}` becomes `{% endif %}`.

Still to settle: `include` with `../` paths and loading from an
`embed.FS` in pongo2, access to modules without a published tag or in
private repositories (`GOPRIVATE`), and the provider contract, which goes
into [`skill-methodology.md`](../skill-methodology.md).

## Two things called onboard

- **The session prompt** (`scripts/bootstrap/onboard`, `prompts/onboard.md`)
  is text the launcher hands to the harness before it starts: the
  bootstrap protocol with persona, mode, signatures and languages filled
  in, followed by the active voice. It belongs to the launcher, and
  `internal/bootstrap/onboard` renders it byte for byte like the Bash
  bootstrap, substituting only its variables where the Bash version
  evaluated the whole template.
- **The orientation protocol** (focus, session resume, context, status or
  ponder) is what the agent does when someone types `onboard`. It belongs
  to the workflow engine and becomes one deterministic command of the flow
  engine, instead of a sequence the agent performs step by step.

## Workflow engine

`jacazul flow` is the door to the workflow engine
(`jacazul-ai/flow`). It receives the project, home and session that
`jacazul` resolved (Runtime defaults) and never resolves or generates its
own:

- Until the engine is embedded, `jacazul flow <args...>` passes through to
  the current `tw-flow` with the same arguments, streams and exit code,
  marked for replacement by `flow.Run`.
- `jacazul flow session list` is implemented in Go. It reads the
  `focus-<id>.json` lanes under `TASKDATA` directly and prints what
  `tw-flow session list` prints (session, plan, task, age, status, `*` on
  the current session), plus a HANDOFF column: `unread` for a handoff note
  not read yet, `read` for one acknowledged with `tw-flow session ack`. The
  header shares the lanes' layout, so its columns line up. It only
  reads, so it does not refresh the lane's age the way every `tw-flow`
  command does. Sessions stay owned by the workflow engine; the launcher
  only creates or accepts the session ID. Other `jacazul flow` commands
  point to `tw-flow` until the pass-through lands.
- `jacazul ui doctor` is implemented in Go, with no Bash predecessor: a
  read-only audit of browser automation servers (see
  [UI Expert](../ui-expert.md)). It reads `/proc` on Linux, `ps` and
  `lsof` on macOS and PowerShell on Windows.

## Parity with the Bash launchers

`DRY=true DEBUG=true` is the observability contract of the Bash launchers:
it shows environment, hatch, skill links and settings without starting the
harness. The Go launcher is held to it:

- `testdata/parity/scenarios.tsv` lists the scenarios; `make parity` (or
  `testdata/parity/capture <harness>`) records each one in a throwaway HOME
  with its own venv, and stores exit code, output, the HOME tree and the
  settings files, with machine paths replaced by placeholders.
- `internal/parity` checks the references and compares them with
  `jacazul --dry --debug <harness>`.
- Both are temporary and leave at the cutoff.

The claude comparison accepts four differences, each on purpose: the
venv sync and hatch lines are absent because neither runs on the launch
path; the Taskwarrior bootstrap announces the task data directory it
creates, which the Python hatch used to create silently; `--resume` keeps
the session prompt and reaches claude; and the task binary path is not
compared, since it differs per machine.

`testdata/parity/capture --exec` also runs the harness step, as
`testdata/parity/fake-claude`, and records the arguments and the
environment the launcher hands to claude (`<scenario>.exec.txt`). The Go
environment matches the Bash one, with these differences:

- The Go launcher adds `JACAZUL_PROJECT` and `JACAZUL_SESSION` (Runtime
  defaults).
- Without `--session` it runs the global session, so `JACAZUL_SESSION_ID`
  stays unset.
- It does not export `CURRENT_DIR`, `PARENT_DIR`, `JACAZUL_PROJECT_ANCHOR`
  or `JACAZUL_PERSONA_SPEC_FILE`, which only the Bash scripts read.

It does export the Bash run-once guard `JACAZUL_ENV_INITIALIZED`. Without
it, a legacy Bash launcher started inside the harness would rerun its
whole bootstrap and mint its own session. The export goes when the legacy
names route through the Go binary.

## Transition and cutoff

1. Harness subcommands land one by one, each checked against its parity
   references.
2. The legacy `jacazul-<harness>` names route to the Go binary.
3. At the cutoff the Bash launchers, `testdata/parity`, `internal/parity`
   and the `parity` target are removed, and `make test` runs the Go suite.

Taskwarrior and `tw-flow` are replaced by the flow engine, which has its
own database. Until then the launcher keeps today's Taskwarrior behavior:
`internal/bootstrap/taskwarrior` ports the Bash bootstrap one to one,
known issues included, with the `.taskrc` templates embedded from
`templates/taskwarrior`. Porting it rather than calling the script keeps
the launcher free of Bash. The flow
cutoff removes the package and migrates the Taskwarrior data into the flow
database; it is a separate step from the Bash launcher cutoff unless the
two coincide.

### Temporary: the launcher finds its checkout

Until the Go hatch embeds them, the skills and
`extensions/claude/jacazul-line.sh` are linked from a checkout of this
repository, as the Bash launchers do from `SCRIPT_DIR/../..`. The launcher
takes that checkout from its own path: `os.Executable()`, resolved through
symlinks, is `<checkout>/bin/jacazul`, and its parent is the checkout.

- `make install` builds `bin/jacazul` and links it as `~/bin/jacazul`
  (`BINDIR=` changes the directory). It is a link, not a copy, so the
  path still resolves into the checkout; running it from another worktree
  repoints the link there.
- It works for `make build` and for the `~/bin` link, from any project
  directory: the project comes from the working directory, the skills from
  the checkout the binary was built in.
- A binary outside a checkout (`go install`, a release download) has no
  `skills/` next to it and stops with an instruction.
- The lookup leaves the launcher when the hatch embeds both the skills and
  the extension; from then on the binary needs no checkout.

`internal/bootstrap/claude` differs from the Bash bootstrap on purpose in
four places: the permission merge always runs (Bash skipped it without
`jq`); a real directory where a link belongs is left alone with a warning
(Bash's `ln -sfn` dropped a stray link inside it); an invalid
`settings.json` stops the launch with an instruction instead of a `jq`
error; and `settings.json` is rewritten only when it changes, atomically,
keeping its mode.

## Out of scope until Jacazul is consolidated in Go

- **Sandboxes.** `JACAZUL_HOME/sandboxes` and the sandboxed launcher
  (`scripts/jacazul-gemini-sandboxed`) are not valid today. The Go launcher
  neither ports nor reproduces them, and the parity matrix has no sandboxed
  scenario. They are revisited only after the whole of Jacazul runs in Go.

## Open decisions

- `--project` and `JACAZUL_PROJECT` take an identity (`jacazul-ai_flow`),
  as implemented, rather than a path. This serves tests and sandboxes,
  their main users; to be confirmed.
- Whether a resumed conversation still skips the onboard prompt.
- Whether the Jacazul session records the harness conversation it started,
  so `jacazul --session ID <harness>` resumes that conversation by itself
  (`-r`, `--session` or `-s`, per harness).
- Whether the Bash launchers call the Go steps during the transition, so
  each rule has one source, or keep their own copies until the cutoff.
