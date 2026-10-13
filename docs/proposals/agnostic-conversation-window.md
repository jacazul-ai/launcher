# Proposal: Agnostic Conversation Window

**Status:** Research. No runtime implementation has landed.
**Audience:** Contributors implementing the Go launcher and harness adapters.
**Related:** [`go-launcher.md`](go-launcher.md), [`go-launcher-migration.md`](go-launcher-migration.md),
[`ARCHITECTURE.md`](../ARCHITECTURE.md).

## Goal

When a user starts a turn in Pi, Codex, or Claude Code, the launcher should
make a bounded recent-history window available without tying the history to a
specific harness. The default window is **50 user/assistant turns**. A turn is
a user prompt plus the assistant result that follows it.

The window is a local continuity aid, not a replacement for a harness's native
transcript, a task record, or a long-term memory system.

## When any harness starts or resumes

Load the window through one Go-owned store. The store must be keyed by the
conversation identity, not by the harness name. The harness and its native
session ID are metadata on each record.

Recommended identity:

```text
window = project identity + conversation profile
record = window + harness + native session ID + turn ID
```

The default conversation profile can be `default`; a future CLI flag can
select another profile when a project needs separate threads. This lets a user
move between Pi, Codex, and Claude without creating three unrelated windows.

The launcher already resolves project, home, and Jacazul session values once
for every harness. The context store should reuse those resolved values rather
than reimplementing project discovery.

## When a harness submits a turn

The adapter asks the Go core for a bounded, model-ready context block. The
core, not the adapter, decides which records fit the configured limits.

The injected block should be:

- explicitly labelled as recent conversation context;
- bounded by both turn count and bytes/tokens;
- treated as reference material, never as instructions that override the
  harness or Jacazul safety rules;
- omitted with a non-blocking warning when the store is unavailable.

Adapters must pass structured data to the Go command through JSON on stdin or
argv values. They must not interpolate prompts into shell commands.

## When a turn finishes

The adapter records the new turn through the same Go core. Writes must be
idempotent because retries, compaction, resumed sessions, and duplicated hook
notifications are possible.

The core then prunes records older than the configured window and retains no
unbounded transcript by accident. A future summarization phase may preserve
older decisions, but summarization is separate from the first 50-turn
implementation.

## Harness adapter matrix

| Harness | Injection boundary | Persistence boundary | Adapter shape |
|---|---|---|---|
| Pi | `before_agent_start`; use the extension lifecycle instead of replacing the whole system prompt | `turn_end` or the final actionable boundary before settlement | Trusted TypeScript extension calls the Go context command or package boundary |
| Claude Code | `SessionStart` for session context and/or `UserPromptSubmit` for a fresh per-turn window | `Stop`/session lifecycle event using the hook payload | Command hook configured by the launcher; JSON arrives on stdin and structured output can add context |
| Codex | `SessionStart` and/or `UserPromptSubmit`; hook output can add developer context | `Stop` for turn completion and `SessionEnd` for final cleanup | Command hook in `hooks.json` or `config.toml`; JSON arrives on stdin |

The exact lifecycle event remains an adapter detail. The Go store, record
schema, pruning policy, identity rules, and security controls stay shared.

### Pi

Pi extensions run in-process as TypeScript modules and expose lifecycle events
through `pi.on()`. `before_agent_start` can adjust prompt sections and
`turn_end`/`agent_before_settle` provide actionable boundaries. The extension
should keep the Go core as the source of truth and use Pi's documented session
state APIs only for Pi-specific state.

The extension must not depend on a long-lived process started from the factory:
Pi can load extensions in modes that do not start a session. Start and close
any process or connection from the session lifecycle, and keep the extension
functional in interactive, RPC, JSON, and print modes.

### Claude Code

Claude Code hooks are configured as commands, HTTP endpoints, MCP tool calls,
LLM prompts, or subagents. For this feature, a local command hook is the
smallest boundary: it receives the event JSON on stdin, invokes the Go
context command, and returns only the bounded context or record result.

`SessionStart`, `UserPromptSubmit`, `Stop`, and `SessionEnd` map naturally to
load, per-turn injection, per-turn persistence, and cleanup. The adapter must
handle hook timeouts and malformed output without silently logging prompt
contents.

### Codex

Codex supports command hooks at `SessionStart`, `SessionEnd`, `UserPromptSubmit`,
`Stop`, and other agent-loop events. `UserPromptSubmit` exposes fields such as
`cwd`, `prompt`, `session_id`, `transcript_path`, and `turn_id`. A command hook
can return plain text or structured `additionalContext` for the model.

Use the event payload as the integration contract. Do not parse
`transcript_path` as the canonical data source: Codex documents that the
transcript format is convenient but not a stable hook interface. Non-managed
hooks also require user review/trust, so installation must leave a visible
trust step rather than bypassing it.

## Go boundary

The first implementation should earn one concrete package and one small CLI
boundary instead of introducing a broad interface hierarchy. A possible
command shape is illustrative:

```text
jacazul context load   --project <id> --profile <name>
jacazul context record --project <id> --profile <name> < turn.json
```

The command boundary should accept a canonical envelope such as:

```json
{
  "project_id": "jacazul-ai_launcher",
  "profile": "default",
  "harness": "pi",
  "session_id": "session-123",
  "turn_id": "turn-456",
  "user": "...",
  "assistant": "..."
}
```

Names and flags are not final. The invariant is that adapters translate their
native event into this envelope; they do not implement storage or window
policy themselves.

## Storage and concurrency

Use `JACAZUL_HOME` for local state, outside the checkout and Git history. The
store needs:

- per-project and per-profile separation;
- restrictive directory/file permissions;
- atomic read-modify-write or an equivalent transaction boundary;
- cross-process locking when multiple harnesses can write concurrently;
- bounded records and explicit size limits;
- recovery from a truncated or malformed final record.

A line-oriented file can be a first implementation if locking, atomic
replacement, and corruption recovery are explicit. A database should not be
introduced only to hide an unmeasured storage problem; choose it later if
concurrent writers or query requirements earn the dependency.

## Security boundary

Conversation history can contain source code, credentials, personal data, and
prompt-injection text. Before implementation:

1. Threat-model every hook as a privileged local process that can read prompts.
2. Redact known secret formats before persistence and never print raw records in
   debug output.
3. Keep the store local with restrictive permissions; do not sync it through
   Git, Taskwarrior annotations, or public artifacts.
4. Keep injected context clearly separated from system instructions and cap its
   size.
5. Use absolute executable paths or a trusted launcher-owned binary; avoid shell
   interpolation of prompt data.
6. Fail open for this non-critical memory feature when loading fails, but emit a
   safe diagnostic. Never block a user turn merely because recent memory is
   unavailable.
7. Provide an explicit clear/delete operation and document its retention
   behavior.

The hook adapters are code-execution surfaces. They must be installed only from
trusted launcher content, and Codex's hook trust review must remain enabled.

## Verification plan

Before calling the feature complete, add tests for:

- pruning to exactly 50 turns;
- byte/token budget enforcement;
- shared access from Pi, Codex, and Claude profiles;
- isolation between projects and profiles;
- duplicate event/idempotent writes;
- concurrent writers and interrupted atomic replacement;
- malformed input and truncated records;
- secret redaction and absence of raw content in diagnostics;
- adapter fixtures for each harness's load and record event.

Run the repository's configured Go gates (`make go-test`, `make vet`, and the
format target) plus a manual smoke test in each harness. The integration tests
must use fake hook payloads and a temporary `JACAZUL_HOME`; they must not read
or mutate the real user's context store.

## Open decisions

- Whether the default profile is project-wide or tied to a Jacazul session.
- Whether the first release stores full assistant output or a bounded excerpt.
- Which secret redaction rules are mandatory and how users review false
  positives.
- Whether old records are deleted permanently or compacted into an explicit
  summary file.
- Whether adapters invoke a `jacazul context` subprocess or link a Go package
  through a future harness integration.

## References

- Pi extensions and lifecycle events: [Pi Extensions documentation](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md)
  and the installed reference at
  [`@earendil-works/pi-coding-agent/docs/extensions.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md).
- Claude Code hook lifecycle, event payloads, command hooks, and output rules:
  [Claude Code Hooks reference](https://docs.anthropic.com/en/docs/claude-code/hooks).
- Codex hook events, configuration, trust review, context output, and limits:
  [Codex Hooks](https://developers.openai.com/de-DE/docs/hooks).
- Codex plugin-bundled lifecycle hooks and managed-hook restrictions:
  [OpenAI Plugins — bundled lifecycle hooks](https://developers.openai.com/plugins/build/plugins).
- Codex configuration and managed-hooks-only setting:
  [Codex configuration](https://github.com/openai/codex/blob/main/docs/config.md).
- Codex `UserPromptSubmit` event schema:
  [`user-prompt-submit.command.input.schema.json`](https://github.com/openai/codex/blob/main/codex-rs/hooks/schema/generated/user-prompt-submit.command.input.schema.json).
- Jacazul Go launcher boundary and shared runtime resolution:
  [`go-launcher.md`](go-launcher.md).
- Prior art for compacting old records, read at commit `6f32daf`: oh-my-pi's
  snapcompact keeps both chronological edges as verbatim text, renders the
  middle as PNG frames a vision model reads back, and re-renders every pass
  from bounded source text instead of carrying old frames forward. The
  edges-plus-bounded-source shape applies here; the image encoding is tuned
  per model and provider, so it does not fit a harness-agnostic store.
  [`packages/snapcompact`](https://github.com/can1357/oh-my-pi/tree/6f32daf/packages/snapcompact)
  and [`docs/compaction.md`](https://github.com/can1357/oh-my-pi/blob/6f32daf/docs/compaction.md).
