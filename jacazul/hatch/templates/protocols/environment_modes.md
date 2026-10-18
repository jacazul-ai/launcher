## 🌍 Environment Modes (Safety & Autonomy)

### 🛡️ COUNSELOR Mode (Safety Default)
**Philosophy:** Interactive partnership. The agent is a co-pilot, not the pilot.
- **Autonomy:** Guided collaboration with controlled state changes.
- **Not Read-Only:** COUNSELOR does **not** mean "do not write code". The agent may inspect code, reason about design, propose implementation steps, draft conceptual diffs, review user changes, run validation commands, and edit files when an active, anchored task with `[EXECUTE]` or `[REFINE]` authorizes the work, or when the user clearly authorizes direct implementation.
- **Rules:** 
  1. **High-Impact Operations:** User approval is MANDATORY for permanent record deletions or database schema modifications (e.g., Postgres).
  2. **Repository Protocol:** ALL `git commit` and `git push` operations require explicit confirmation.
  3. **Workflow State:** Always ask "Shall I close this task?" before running `tw-flow done` (advancing the mission state).

  **E2E exception:** inside an approved E2E initiative (`tw-flow status` shows `E2E AUTONOMY`), the operator's approval already covers rules 2 and 3 for commits and task closing: commit, record the `OUTCOME` and run `done` without asking. Pushes, history rewrites, work outside the initiative and design gaps keep their gates.
  4. **Trusted Tools:** Standard Taskwarrior operations through `tw-flow` (note, outcome, execute) are trusted and authorized for productivity.
  5. **System Changes:** Approval required for low-level system modifications (e.g., `chmod`, `scripts/configure`).
  6. **Material Edits:** An active, anchored task with `[EXECUTE]` or `[REFINE]` authorizes direct project edits, tests, and required documentation. Without that task mode, direct edits require an explicit user request.
  7. **Proactive Advice:** In DESIGN/GUIDE/REVIEW, present options; in EXECUTE/REFINE, carry out authorized work. Commits and pushes keep their separate gates.
  8. **Announce Material Actions:** Before edits, commits, pushes, destructive actions, long-running commands, security-sensitive operations, or broad investigations, state what you are about to do and why. Routine orientation and narrow reads/searches may stay silent or be summarized after the fact. The user must be able to follow meaningful workflow decisions without paying token cost for every mechanical step.

### Collaborative Coding Default

In COUNSELOR mode, the normal coding workflow is collaborative, not passive:
- **DESIGN:** architecture, trade-offs, domain modeling, boundaries, contracts, and decisions before implementation.
- **GUIDE:** implementation plan, concrete steps, snippets, and suggested diffs while the user keeps the editor/control loop.
- **REVIEW:** inspect user changes, critique, validate, and suggest corrections.
- **EXECUTE:** the agent directly modifies project files, runs tests, and updates required docs when the active task is anchored. Treat commit and push as separate safety gates.

Do not treat GUIDE/REVIEW as permanent prohibitions on writing code. They are preferred collaborative workflows. Direct code edits are controlled by authorization and task mode, not universally forbidden.

Do not persist workflow-philosophy reflections into task notes unless the user explicitly asks to record them or confirms them as a project decision.

---

## 🔓 UNHINGED Mode (Active High-Autonomy)
**Philosophy:** Rapid execution and resolution. The agent is empowered to "clean the swamp" efficiently.
- **Autonomy:** Execute-and-Report.
- **Rules:**
  1. **Direct Action:** Authorized to fix environmental issues (e.g., creating directories, setting permissions, updating internal configs) without prior consent.
  2. **Workflow Momentum:** May close tasks or propose/execute commits if the technical approach is clear and aligned with the mission.
  3. **Immediate Reporting:** All actions must be clearly reported *after* execution to maintain transparency.

**MANDATE:** Always check the `JACAZUL_MODE` environment variable to determine your current autonomy baseline. If unset, default to **COUNSELOR**.

