# Pi Durable and Jacazul

## Research status

This document records an architecture investigation. It is not an adoption
decision and does not replace the existing Jacazul launchers.

## I want durable agent execution

Use Pi Durable when an agent must survive process crashes, restarts, eviction,
or a disconnected client.

Pi Durable is a TypeScript framework for building agentic applications. It is
not a flag or a mode of the Pi coding-agent CLI. A `Harness` opens a storage
backend and runs conversations, model turns, tool calls, retries, compaction,
and application tasks over that storage.

The durable unit is a conversation and its task graph:

```text
input
  -> generation task
      -> tool tasks
  -> assistant answer
```

The harness commits state before exposing it. A restarted process can reopen
the same storage, resume unfinished work, and continue from the last
checkpoint.

## I want prompt and tool injection

Register Jacazul capabilities as Pi Durable extensions.

An extension can provide:

- system-prompt sections rendered before model requests;
- tools with typed arguments and structured results;
- hooks around model and tool tasks;
- wrappers that replace or decorate tools;
- durable tasks and application state;
- reloadable implementations.

The package already provides coding tools for `read`, `write`, `edit`, and
`bash`. Jacazul-specific prompt sections can render the engine, active persona,
project identity, focus, or other committed state without copying the whole
prompt into every client.

## I want crash-safe tool execution

Declare a tool `replay: "safe"` only when running it again after an interrupted
call is harmless. Reads and idempotent whole-file writes are candidates. An
edit, deployment, payment, or external side effect must remain unsafe unless
it has its own idempotency key and recovery contract.

An unsafe tool interrupted by a crash is reported to the model as interrupted;
Pi Durable does not blindly repeat it. This is safer than claiming exactly-once
execution for arbitrary external effects.

## I want multiple conversations or clients

A single harness can host multiple conversations, forks, foreground tasks, and
background tasks. Clients can attach late and receive a current view containing
the transcript, pending input, running tools, and usage.

Pi Durable does not prescribe a UI or chat protocol. A Jacazul host can expose
sessions through a CLI, RPC, WebSocket, HTTP API, Neovim integration, or a web
client.

## I want to use Cloudflare

Use Cloudflare's beta `PiHarness` integration when the durable runtime should
live inside a Cloudflare Agent or Durable Object.

The integration provides:

- Pi Durable storage in the Durable Object's SQLite database;
- lifecycle wake-ups while a session has unfinished work;
- recovery after eviction, restart, or crash;
- Workers AI and AI Gateway model integration through `pi-ai`;
- session methods that can be exposed through HTTP, WebSocket, or RPC.

`PiHarness` supplies hosting lifecycle and storage. Pi Durable still owns the
transcript, inbox, model turns, tools, retries, and recovery rules. It does
not provide the client protocol or UI. The Cloudflare API is beta and may
change while Pi Durable evolves.

## I want to integrate Claude, Pi, or OpenCode

Do not assume that tools from another coding harness are portable packages.
There are two safe boundaries:

1. **Native runtime:** implement or register the capability as a Pi Durable
   tool or extension.
2. **Adapter:** expose an external harness capability through a deliberate
   bridge with an explicit timeout, permission boundary, replay policy, and
   idempotency behavior.

The current Jacazul launchers invoke the Pi, Claude, and OpenCode CLIs as
separate runtimes. They do not share a common durable tool registry.

OpenCode v2 also has its own durable session and recovery design. That is a
separate implementation, not evidence that OpenCode uses `@earendil-works/
pi-durable`. Jacazul should avoid stacking two durability systems around the
same run without defining ownership of storage, retries, and tool effects.

## Relevant examples

The upstream examples map directly to the proposed Jacazul investigation:

| Example | Relevance |
|---|---|
| `13-recovery.ts` | Resume unfinished work after a restart |
| `15-system-prompt.ts` | Render dynamic system-prompt sections |
| `17-coding-tools.ts` | Register coding tools |
| `20-inbox.ts` | Queue pending inputs |
| `21-late-join.ts` | Attach a client to an active conversation |
| `22-subagent-foreground.ts` | Run owned foreground subagents |
| `23-subagent-background.ts` | Run background work |
| `24-child-tasks.ts` | Build task ownership trees |
| `26-coding-agent.ts` | Assemble a coding agent |
| `27-plan-mode.ts` | Add a planning mode |
| `28-reviewer.ts` | Add a reviewer agent |
| `29-sandbox-per-conversation.ts` | Isolate execution per conversation |
| `31-reload-and-restart.ts` | Reload extensions and recover after restart |

## Proposed Jacazul boundary

The first Jacazul implementation should treat Pi Durable as an optional
runtime, not as an immediate replacement for the existing launchers:

```text
Jacazul engine
  ├── persona and system-prompt extensions
  ├── project and Taskwarrior tools
  ├── broker and Git tools with explicit permissions
  ├── Pi Durable harness
  │     ├── SQLite or JSONL storage
  │     ├── durable conversations and tasks
  │     └── replay-aware tool registry
  └── clients: CLI, RPC, Neovim, web, or Cloudflare
```

The existing Pi, Claude, and OpenCode launchers can remain compatibility
clients while the durable runtime is validated separately. This keeps the
current local workflows stable and prevents a durable-runtime experiment from
changing every harness at once.

## Recommended proof of concept

Before adopting Pi Durable as a Jacazul runtime, build a small isolated
prototype that proves:

1. a local SQLite-backed `Harness` opens and resumes;
2. a Jacazul system-prompt extension renders the active persona and project;
3. `CodingTools` and one Jacazul tool run through the registry;
4. a process killed during a model turn or tool call resumes correctly;
5. safe and unsafe replay policies produce the expected outcomes;
6. two clients can observe and steer one conversation;
7. Taskwarrior access stays behind `taskp` or `tw-flow`, never raw `task`;
8. secrets and tool output do not leak into transcripts or logs.

Only after the local proof is green should the Cloudflare `PiHarness` become a
second storage and lifecycle target.

## Boundaries and risks

- Pi Durable is experimental; its API may change.
- Cloudflare `PiHarness` is beta.
- Pi Durable currently has no built-in approval or permission step for tools.
- Event streams begin from a snapshot rather than an arbitrary replay cursor.
- Long-running Cloudflare work is constrained by Durable Object lifecycle and
  alarm limits.
- Replay safety is a tool contract, not a guarantee that arbitrary external
  effects are exactly once.
- Adding the runtime introduces a TypeScript dependency and supply-chain
  surface that requires a separate dependency-security review.

## Sources

- [Pi Durable announcement](https://earendil.com/posts/pi-durable/)
- [Pi Durable package README](https://github.com/earendil-works/pi/tree/main/packages/durable)
- [Pi Durable examples](https://github.com/earendil-works/pi/tree/main/packages/durable/test/examples)
- [Cloudflare Pi Harness](https://developers.cloudflare.com/agents/harnesses/pi/)
- [OpenCode v2 session specification](https://github.com/anomalyco/opencode/blob/dev/specs/v2/session.md)
