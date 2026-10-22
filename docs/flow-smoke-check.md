# Flow Smoke Check 🔥

Run this when you want to trust `jacazul flow` on a project before it
migrates for real: after moving the engine pin, after changing the storage
check (`internal/cli/storage.go`), or before the first `jacazul flow`
command on a project that still lives in Taskwarrior. The check proves two
things: the storage lands where it should, and the Taskwarrior silo is never
written.

Why and how opening a project works: "Opening a project" in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## 1. Build the launcher

From the launcher checkout:

```bash
go build -o /tmp/jacazul ./cmd/jacazul
```

## 2. Record the silo

The silo is `~/.jacazul-ai/.task/<PROJECT_ID>`. The dry run in the next step
prints the project ID if you do not know it.

```bash
SILO=~/.jacazul-ai/.task/<PROJECT_ID>
sha256sum "$SILO/taskchampion.sqlite3" > /tmp/silo.sha
```

On Taskwarrior 2 the file is `pending.data`.

## 3. Dry run in the project

In the project directory:

```bash
/tmp/jacazul --dry flow status     # or: DRY=true /tmp/jacazul flow status
```

You see:

```text
🐊 jacazul flow (dry): nothing is written
   database  /home/<you>/.jacazul/projects/<PROJECT_ID>/flow.sqlite3 (missing)
   silo      /home/<you>/.jacazul-ai/.task/<PROJECT_ID> (Taskwarrior data)
   task      /usr/bin/task
   action    migrate a copy of the silo
Migration dry-run: no changes written
Records: created=... dependencies=... annotations=... tags=... issues=...
```

| Line | It is right when |
|---|---|
| `database` | it sits under `~/.jacazul/projects/<PROJECT_ID>/`, unless you set `JACAZUL_FLOW_DATABASE_PATH` |
| `silo` | it is the project's directory under `~/.jacazul-ai/.task/` and says `Taskwarrior data` |
| `task` | it is the real binary, never `.../scripts/task` (the Jacazul guard) |
| `action` | `migrate a copy of the silo` for a project not migrated yet, `use the flow database` after |
| report | `no changes written`, and no `ERROR` lines; `WARNING` lines are records the engine kept in another form |

## 4. Prove nothing was written

```bash
sha256sum -c /tmp/silo.sha                       # OK
ls ~/.jacazul/projects/<PROJECT_ID>              # No such file or directory
ls -d "${TMPDIR:-/tmp}"/jacazul-migrate-*        # no matches: the copy is gone
```

## 5. Apply in a sandbox (optional)

To see the real migration without touching your homes, run it on a copy
with a scratch `HOME`:

```bash
S=$(mktemp -d)
mkdir -p "$S/legacy/.task" "$S/home"
cp -a "$SILO" "$S/legacy/.task/"
sha256sum "$S/legacy/.task/<PROJECT_ID>/taskchampion.sqlite3" > "$S/copy.sha"

HOME="$S/home" JACAZUL_HOME= TASKDATA= \
  /tmp/jacazul --home "$S/legacy" --project <PROJECT_ID> flow status
```

`🔄 jacazul flow: migrating ...` and `Migration applied` go to stderr, then
`status` runs on the new database in `$S/home/.jacazul/projects/`. Run the
same command again: it must not migrate a second time. Then:

```bash
sha256sum -c "$S/copy.sha"    # the copy of the silo is unchanged too
rm -rf "$S"
```

## When it fails

| You see | Meaning | Next |
|---|---|---|
| `action ask: install Taskwarrior ...` | no real `task` was found | install Taskwarrior, or set `JACAZUL_REAL_TASK` |
| `Taskwarrior export failed: ...` | `task` refused the copy; its own message follows | fix what `task` says; the silo was not changed |
| `decode Taskwarrior export: ...` | the export has a value the engine cannot read | report it to the engine (`jacazul-ai/flow`) with the field name |
| `ERROR` lines in the report | records the engine could not migrate | read them before the first real `jacazul flow` command |
| `sha256sum: FAILED` | the silo changed | stop and report it: the storage check must never write there |
