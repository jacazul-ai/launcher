---
name: taskwarrior-expert
description: Expert system for managing session plans, tasks, and context using Taskwarrior. Use this when managing tasks, creating plans, tracking progress, or storing session context.
license: MIT
---

# Instructions

# Taskwarrior Integration Protocol

## 🏗️ Per-Project Database Architecture (v1.6.0)

Taskwarrior uses **isolated databases per project** for isolation and performance.

### PROJECT_ID Variable
The `PROJECT_ID` environment variable is automatically set by the bootstrap script from the canonical project anchor:
- regular Git repo → `git rev-parse --show-toplevel`
- linked worktree with shared `.git`/`.bare` → parent of the common Git directory
- fallback outside Git → current directory

The final value remains:
```bash
PROJECT_ID="${PARENT_DIR}_${CURRENT_DIR}"
```

### Database Structure
Each project has its own database at `~/.jacazul-ai/.task/$PROJECT_ID/`.

### Project-Aware Tools
Main tools automatically detect and use the correct project database:
1. **taskp**: Project-aware wrapper.
2. **tw-flow**: Workflow management with TASKDATA support.
3. **tw-flow ponder**: Dashboard with per-project views.
   - *Note: The standalone "ponder" command is deprecated and will be removed in a future release.*
4. **jacazul-hatch**: JIT Prompt Forge engine.
5. **jacazul-persona**: Persona switching manager.

All tools set `TASKDATA=~/.jacazul-ai/.task/$PROJECT_ID` automatically.

## 🔑 UUID and Language

- Refer to tasks by short UUIDs (8 chars), never numeric IDs:
  `fa145ef2 - Task description [urgency]`.
- Store every task description, annotation and tag in English; answer in the
  session language.
- Interaction modes (`[DESIGN]`, `[GUIDE]`, `[EXECUTE]`…) and what each one
  authorizes: jacazul-engine hub, "Interaction Modes".

## ⚖️ Urgency Calibration Protocol (Cool Down)

To maintain a high-fidelity tactical radar, agents MUST follow the **Cool Down** protocol for task creation:

1.  **Default Chill:** New tasks MUST NOT have a default `due` date. Only assign a `due` date if explicitly requested or logically mandatory.
2.  **Priority Neutral:** Default all tasks to `priority:M`. Avoid `priority:H` during plan creation unless it's an immediate blocker.
3.  **Just-in-Time Heat:** Urgency elevation (priority changes, due dates) should primarily happen during `tw-flow focus` or roadmap transitions.
4.  **Safe Quoting:** Always quote project names in CLI commands to prevent Taskwarrior expression parsing errors (e.g., `taskp project:"plan-name" export`).

## 💡 Best Practices

1. **Simple Descriptions:** Use clear descriptions like "Implement user auth" instead of prefixing with project names.
2. **Isolated Silos:** Tasks from different projects NEVER mix. Trust the silo isolation.
3. **Outcome First:** Never close a task without an `OUTCOME` annotation for context propagation.

---

## 🛠️ Core Tools Reference

- **`tw-flow ponder`**: High-fidelity project dashboard.
   - *Note: The standalone "ponder" command is deprecated and will be removed in a future release.*
- **`tw-flow`**: Standardized task management with context propagation.
- **`taskp`**: **CRITICAL** Project-Aware Taskwarrior Wrapper. Always use `taskp` instead of raw `task`.
- **Output cache:** `tw-flow status` and `tw-flow ponder` print
  `🐊 [cached]` when nothing changed; trust the last full output and bypass
  only with `tw-flow status --force` or `tw-flow ponder --force`. Cache rules
  and TTLs: jacazul-engine `references/onboard.md`.

## 🔄 Session Handoff

```bash
tw-flow session resume        # Print previous session note (silent if none) — run on onboard
tw-flow session dump          # Create handoff note for the next session
tw-flow session dump --force  # Overwrite existing note
```

Resuming the session (`--jacazul-session <id>`) delivers a pending note in
the opening prompt until `tw-flow session ack` marks it read. When
and how to fill the note, and what to show the user: jacazul-engine
`references/session.md`.

---

## 🎯 Independent Focus Mode

Sessions can be isolated from the global `focus.json` using `JACAZUL_SESSION_ID`.

**Commands:**
```bash
tw-flow focus ind plan <name>       # Anchor to plan in independent session
tw-flow focus ind task <uuid>       # Anchor to task in independent session
tw-flow focus ind <plan-name>       # Smart focus in independent mode
tw-flow focus back                  # Exit independent mode, delete session file, return to global focus
tw-flow focus clear                 # Reset plan/task anchors in active file (does NOT delete session file)
```

**Bootstrap pre-seed (via env vars):**
```bash
JACAZUL_FOCUS_PLAN=my-plan JACAZUL_FOCUS_TASK=<uuid> jacazul-claude
```
The taskwarrior bootstrap will create `focus-{SESSION_ID}.json` automatically.

**Rule:** If `JACAZUL_SESSION_ID` is set, ALL focus reads/writes go to `focus-{SESSION_ID}.json`. The global `focus.json` is never touched by an independent session.
**Distinction:** `focus back` exits the independent session (deletes session file). `focus clear` only zeroes the plan/task anchors within the current active file.

---

## 🚀 Quick Start Guide

### 1. Create a Plan
```bash
tw-flow plan feature-x \
  "DESIGN|Design schema|research" \
  "EXECUTE|Implement POST|implementation"
```

### 2. Work on a Task
```bash
tw-flow execute <uuid>
tw-flow note <uuid> decision "Using library Y."
tw-flow outcome <uuid> "Result achieved."
tw-flow done <uuid>
```

### 3. Check Status
```bash
tw-flow ponder          # Horizon View (Global)
tw-flow status          # Hands-on View (Focused)
```
