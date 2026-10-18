# 🐊 tw-flow session

Agent session management — restore context, not conversation.

> For operational plans and tasks, see [tw-flow.md](tw-flow.md).
> For the roadmap ledger, see [tw-flow-roadmap.md](tw-flow-roadmap.md).

---

## The Problem

AI agents have a fundamental asymmetry: their **working memory**
(context window) degrades continuously, while the **project state**
(Taskwarrior tasks, decisions, outcomes) is deterministic and permanent.

As a session runs longer, the agent loses track of earlier decisions,
forgets why a particular approach was chosen, and starts making
inconsistent moves. The conversation history is not a reliable anchor —
it is noisy, compresses poorly, and is agent-specific (Claude history
does not transfer to Gemini).

The Jacazul state is different. Every decision, research finding, and
outcome is stored as a structured annotation in Taskwarrior — not in the
conversation. This means the **mission state is always recoverable**,
independent of how degraded the current context window is.

`tw-flow session` operationalizes this: it provides the tools to capture
what the agent knows at peak clarity, and inject it deterministically on
the next startup — giving a cold agent the exact situational awareness
it needs to continue without interruption.

---

## Concepts

### Jacazul Session vs CLI Session

| | Jacazul Session | CLI Session |
|---|---|---|
| **Stored in** | `focus-{SESSION_ID}.json` | CLI-specific (e.g. Claude `--resume`) |
| **Contains** | Task focus, plan anchor, task track | Conversation history |
| **Reliability** | Deterministic — always recoverable | Degrades over time |
| **Scope** | Any agent (Claude, Gemini, Copilot) | Agent-specific |

The CLI `--resume` flag is for conversation continuity. The Jacazul
session is for **mission continuity** — independent of which agent or
conversation picks it up.

### Session File

Each independent session creates `focus-{SESSION_ID}.json` in
`$JACAZUL_HOME/.task/{PROJECT_ID}/`. The file stores:

- `focused_plan` — active plan name
- `focused_task_uuid` — anchored task
- `task_track` — navigation history

A session file only exists when `tw-flow focus ind` is used. The global
`focus.json` is used by default and is never listed or purged.

---

## Commands

```bash
tw-flow session list                    # List all independent sessions
tw-flow session dump                    # Generate introspective handoff note
tw-flow session resume                  # Print previous session handoff note (silent if none)
tw-flow session purge                   # Remove orphan session files
```

---

## tw-flow session list

Shows all `focus-*.json` files with live status.

```
SESSION ID   PLAN               TASK       AGE    STATUS
7533158a  *  roadmap-engine     28714fce   12m    active
eb417008     roadmap-engine     b113d535   1d     idle
651c3b75     arnalbam           c4db7db2   4d     orphan
```

`*` marks the current session (`$JACAZUL_SESSION_ID`).

### Heartbeat (mtime-based)

Session liveness is tracked via file modification time —
`os.path.getmtime()`. Cross-platform: works on Windows PowerShell,
Linux, and macOS without PID or daemon dependencies.

Every `tw-flow` command touches the active session file via
`os.utime(focus_file, None)` to keep mtime fresh.

| Age | Status |
|---|---|
| < 2h | `active` |
| 2h – 8h | `idle` |
| > 8h | `orphan` |

---

## tw-flow session dump

Generates a structured handoff note for the current session.

### When agents trigger dump

**Propose first (ask the user):**
- User signals session end: "vou fechar", "fechando aqui", "to indo", "até mais", "closing", "wrapping up", "i'm out"

**Execute immediately (no confirmation needed):**
- Explicit request: "dá um dump", "congela o estado", "salva o estado", "bora reiniciar", "do a dump", "freeze state", "save state", "restart session"
- Context degradation: "contexto tá zoado", "tá confuso", "perdeu o fio", "lost track", "context is messed up", "i'm confused"

For context degradation, the agent runs dump and informs:
> "Contexto salvo. Recomendo reiniciar com: `jacazul-<agent> --jacazul-session {SESSION_ID}`"

```bash
tw-flow session dump
# → writes session-note-{SESSION_ID}.md
```

### What it captures

The core signal is the **gap** between what was planned and what is
actually happening. This gap is what context degradation erases — and
what no task annotation fully captures.

A task can say `[EXECUTE] Implement roadmap init guard`. It cannot say
"we got halfway through, the tricky part is that `taskp done` is
intercepted by the workflow enforcement and needs `tw-flow outcome`
first, and we haven't run the tests yet." That knowledge only exists
in the agent's active context. `session dump` extracts it before it
disappears.

**Collected automatically from Taskwarrior + git:**
- Current focus (plan + task UUID)
- Full inherited context: all `DECISION`, `OUTCOME`, `RESEARCH`
  annotations from the task lineage
- `git diff --stat` of uncommitted files
- Pending tasks in the active plan with their urgency

**Filled in by the agent** — a single open `<!-- FILL IN -->` section.
Write whatever is not captured by code or tasks: where execution stopped,
non-obvious state, gotchas, and the single next concrete action to take on resume.

### File behavior (Error as Prompt)

The command will not silently overwrite an existing file:

- **First call:** Creates the file with `<!-- FILL IN -->`. Fill it in now.
- **File exists + `<!-- FILL IN -->` present:** You already ran dump and did not fill it in. Go fill it — do not regenerate.
- **File exists + no `<!-- FILL IN -->`:** A previous agent already filled this in. Read it first — it has the context you are missing.
- **`--force` flag:** Overwrite unconditionally.

### Delivery at launch

```
jacazul-claude / jacazul-pi / jacazul-gemini --jacazul-session {SESSION_ID}
        ↓
Bootstrap finds session-note-{SESSION_ID}.md without acknowledged:
        ↓
Appends it verbatim to the opening prompt as "📋 Session Handoff",
with the instruction: tw-flow focus, tw-flow session ack, continue
from the handoff's next action
        ↓
tw-flow session ack appends "acknowledged: <timestamp>"
```

The launcher only reads the note and writes nothing to it. Until the agent
runs `tw-flow session ack`, every launch of the session delivers the note
again, so a crash before the ack never loses the handoff. The
`acknowledged:` marker is the only state; a note that carries it is never
injected. The Go launcher does not deliver the note yet.

---

## tw-flow session resume

Prints the handoff note left by the previous session. It remains silent when
no note exists. An injected but unacknowledged note is replayed for recovery;
a note with an `acknowledged:` marker reports its state without replaying
contents.

```bash
tw-flow session resume
```

Called as **step 1 of the onboard protocol when anchored**. The agent cannot miss what is already printed on screen, and an acknowledged note remains visible as a diagnostic signal.

### Handoff visibility during onboard

When an explicit onboard, handoff, resume, or status request finds relevant
session context, the agent must report the operational facts in the next
response, including:

- focused plan and task;
- relevant decisions, research, and outcomes;
- repository and worktree state;
- blockers, risks, and concrete next actions.

A confirmation such as `context loaded` is not sufficient. Secrets,
credentials, host details, and private lab evidence remain redacted. Casual
greetings do not trigger this reporting contract; a follow-up asking whether
the handoff was read does.

---

## tw-flow session purge

Removes session files with `orphan` status (mtime > 8h).

```bash
tw-flow session purge           # Preview orphans
tw-flow session purge --confirm # Actually delete
```

The global `focus.json` is never purged.

---

## Resume a Session

When a session exits, the wrapper prints:

```
╭─ 🐊 Jacazul Session ───────────────────────────────────────╮
│  To resume: jacazul-claude --jacazul-session 7533158a      │
╰────────────────────────────────────────────────────────────╯
```

On the next launch with `--jacazul-session <id>`, the bootstrap sets
`JACAZUL_SESSION_ID=<id>` and `tw-flow` automatically picks up
`focus-{id}.json` — restoring the exact mission state without any
manual `tw-flow focus ind`.

### How it works

The `--jacazul-session <id>` flag is parsed in each wrapper **before**
sourcing the bootstrap environment:

```bash
# Parse BEFORE source bootstrap/environment
for i in "$@"; do
    if [[ "$i" == "--jacazul-session" ]]; then _next=true
    elif [[ "${_next:-false}" == "true" ]]; then
        export JACAZUL_SESSION_ID="$i"; _next=false
    fi
done

source "$BOOTSTRAP_ENV"  # guard: if [ -z "$JACAZUL_SESSION_ID" ] → preserves it
```

The bootstrap guard `if [ -z "$JACAZUL_SESSION_ID" ]` preserves the
restored ID instead of generating a new UUID.

The wrappers use a regular process call instead of `exec`, keeping the
shell alive for the exit banner. Banner only shown if a focus file
exists — global sessions get no banner.

```bash
# Launch CLI (no exec — shell stays alive)
"$CLAUDE_BIN" --append-system-prompt "$ONBOARD_PROMPT" "${CLEAN_ARGS[@]}"

# Exit banner — only if independent session file exists
FOCUS_FILE="$JACAZUL_HOME/.task/$PROJECT_ID/focus-$JACAZUL_SESSION_ID.json"
if [ -f "$FOCUS_FILE" ]; then
    echo "╭─ 🐊 Jacazul Session ───────────────────────────────────────╮"
    echo "│  To resume: jacazul-claude --jacazul-session $JACAZUL_SESSION_ID      │"
    echo "╰────────────────────────────────────────────────────────────╯"
fi
```

---

## Autonomous Orchestration (Future Direction)

`tw-flow session dump` is designed as a building block for autonomous
multi-agent orchestration — not just a manual developer tool.

An agent running in a long session can detect its own context
degradation (reasoning quality drop, inconsistent decisions, increasing
uncertainty) and trigger a handoff **without human intervention**:

```
Agent detects degradation
        ↓
tw-flow session dump   ← introspection + gap captured at peak clarity
        ↓
MCP / API call → Orchestrator
        ↓
New agent instance launched with --jacazul-session <id>
        ↓
Bootstrap injects session-note once
        ↓
Mission continues from exact state
```

The orchestrator is stateless — it only moves the session pointer. All
mission state lives in Taskwarrior and the session note. The incoming
agent gets the same situational awareness the previous agent had at its
clearest moment, not at its most degraded.

This is a **self-healing context loop**: the system compensates for the
fundamental limitation of finite context windows without requiring a
human to notice the degradation and intervene.

The MCP/API interface for the orchestrator call is out of scope for the
current `session-resume` plan — tracked as a future initiative.

---

**Status:** Design in progress — `session-resume` plan
**Last Updated:** 2026-04-04
