# Taskwarrior Expert Skill

Agent behavior guide for the `taskwarrior-expert` skill — a structured workflow system for managing tasks, initiatives (plans/inis), and session context using Taskwarrior.

> For CLI command reference, see [tw-flow.md](tw-flow.md).
> For output caching, see [tw-flow-cache.md](tw-flow-cache.md).

---

## 🎯 Overview

The `taskwarrior-expert` skill transforms Taskwarrior into a structured workflow engine. It defines:
- A **7-phase workflow** for consistent task execution
- **8 interaction modes** controlling agent autonomy levels
- **Per-project isolation** via `PROJECT_ID` detection
- **Context preservation** via structured annotations and inherited context

**Terminology:** `plan` and `ini` (initiative) are aliases — both refer to the same concept (a task aggregator). Accept either term interchangeably.

---

## 📋 The 7-Phase Workflow

### Phase 1: Orient (Ponder)
Understand the current state before acting.
```bash
tw-flow ponder
```
- **Initiative Landscape:** Summary of active/ready tasks per initiative.
- **Tactical Readout:** Columnar table showing Status, UUID, Mode, and Urgency.

---

### Phase 2: Initiative (Decide)
Break down goals into actionable dependency chains.
```bash
tw-flow plan <name> <tasks...>
```
Task format: `"MODE|description|tag|due_offset"`

---

### Phase 3: Execute (Act)
Start working on the highest priority ready task.
```bash
tw-flow execute <uuid>
```
**Context Propagation:** Displays inherited `OUTCOME`, `DECISION`, and `LESSON` notes from parent tasks automatically.

---

### Phase 4: Context (Record)
Document work as you go for future reference.
```bash
tw-flow note <uuid> <type> <message>
```
Types: `research` (r), `decision` (d), `blocked` (b), `lesson` (l), `question` (q), `hypothesis` (y), `outcome` (o), `note` (n), `link`.

`tw-flow` automatically appends a provenance signature to persistent agent
communication:

```text
— <Active Persona> (<Current Model>; harness: <Harness>; session: <Session>)
```

This task signature is used for notes, outcomes, handoffs, optional
completion notes, and automatic discard audits. It is separate from the visual
signature used in prompts.

---

### Phase 5: Review (Verify)
1. Summarize accomplishment.
2. Show results (code, output, tests).
3. Ask user: "Shall I close this task?"

---

### Phase 6: Outcome (Capture)
Record final results BEFORE closing. **Mandatory** for `tw-flow done`.
```bash
tw-flow outcome <uuid> "What was achieved"
```

---

### Phase 7: Close (Finalize)
```bash
tw-flow done <uuid>
```
Checks for newly unblocked tasks and updates initiative progress.

---

## 🔁 E2E Development

When you want a whole initiative developed end to end, ask for it in any
language: "desenvolve isso e2e", "termina isso e2e", "take care of this
e2e". The agent then follows one procedure, carried by the
`jacazul-engine` skill:

1. Opens the initiative (DESIGN, EXECUTE, TEST, REFINE) with a ticket and
   focus on the first task.
2. Closes the contract with you: behavior, scope, risks, exclusions and
   acceptance criteria, recorded in the DESIGN task.
3. Waits for your explicit approval. Nothing is implemented before it.
   The approval gives the agent autonomy for the rest of the initiative:
   it commits, closes each task with an `OUTCOME` and moves the focus to
   the next task without asking you each time.
4. Implements one task at a time, test first, with the gates of whatever
   is being implemented and atomic commits: one logical change per
   commit, so the trail stays easy to review, revert and edit.
5. Validates, then shows you files, behavior, tests, commits, ticket and
   focus.
6. Lists the commits and asks: keep the trail and push, or edit it first
   (fixup, squash, drop, reword). Nothing is pushed without your OK.

The autonomy ends at the initiative: pushing, rewriting history, touching
other initiatives and filling a design gap still need you.

`e2e` alone, or anything about end-to-end tests, does not start it.

---

## 🚦 Interaction Modes

| Mode | Behavior | Edit Authority | Use When |
|---|---|---|---|
| **[DESIGN]** | Architecture, trade-offs, boundaries, and breakdown | No direct edits unless authorized | Need requirements consensus |
| **[INVESTIGATE]** | Code exploration | Read-only by default | Unknown codebase |
| **[GUIDE]** | Step-by-step guidance, snippets, and suggested diffs | User keeps the wheel; direct edits require escalation | User wants manual control |
| **[EXECUTE]** | Building/Coding | Direct file edits authorized by task or request | Approach is clear |
| **[TEST]** | QA & Verification | Tests/validation within task scope | Need validation |
| **[DEBUG]** | Root cause analysis | Read-only by default; proposes fixes | Something is broken |
| **[REVIEW]** | Code audit | Review-first; direct edits require escalation | Quality check needed |
| **[PR-REVIEW]** | Readiness check | Review-first; direct edits require escalation | Before merging |

---

## 🛡 Security & Process Enforcement

### 1. Mandatory OUTCOME Record
`tw-flow done` enforces the presence of an `OUTCOME:` annotation. If missing, the command blocks and provides instructional guidance.

### 2. Taskp Vaccination (Command Interception)
The `taskp` wrapper intercepts:
- **Blocked:** `taskp <uuid> done` — must use `tw-flow done`
- **Blocked:** Manual addition of `+DISCARDED` tag — must use `tw-flow discard`

### 3. Automatic Discard Audit
`tw-flow discard` maintains a full audit trail:
- Moves task to `_archive` project
- Adds `+DISCARDED` tag
- Auto-annotates with `OUTCOME: Task discarded and moved to archive.`

### 4. Prompt Marketing & Workflow Awareness
If a focused task has an `externalid` attached (directly or inherited), a tactical alert is displayed:
```
🐊 ALERT: Inherited ticket detected (#16). Git-expert will use this for automated commit referencing.
```

### 5. Completed Task Protection
Commands that modify task state (`execute`, `done`, `note`, `ticket`, `outcome`, `handoff`) are blocked for COMPLETED tasks. The system recommends `amend` for metadata fixes or `reopen` for additional work.

---

## 💡 Best Practices

1. **Use UUIDs:** Always refer to tasks by their 8-character UUID. Never show numeric IDs.
2. **One Active Task:** Avoid multiple active tasks in the same initiative.
3. **Structured Notes:** Use prefixes (`RESEARCH:`, `DECISION:`) for easy context retrieval.
4. **Persistence Guard:** Do not store workflow-philosophy reflections in task notes unless the user explicitly asks to record them or confirms them as a project decision.
5. **Never Bypass Abstractions:** Use `taskp` or `tw-flow`. Never invoke raw `task` directly.
6. **Urgency Calibration:** Only set `due` for real deadlines. Reserve `priority:H` for tasks that are blocking others or have external commitments.

---

**Version:** 1.8.0
**Last Updated:** 2026-03-28
