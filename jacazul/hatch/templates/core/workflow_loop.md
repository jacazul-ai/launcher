## 📋 The Workflow Loop

### Phase 0: Orient (Context-First)
**CRITICAL:** Before touching the filesystem, you MUST understand the mission state.
1.  **Task Context**: Run `tw-flow context <uuid>` on the active or hottest task to read previous outcomes and decisions.
2.  **Source of Truth**: If a task is marked `done` with an `OUTCOME`, trust that outcome. Do NOT re-investigate.
3.  **Search Throttling**: Broad searches (recursive greps) are forbidden unless the agent has already read specific files mentioned in history or task context.

### Phase 1: Orient (Status/Ponder)
Before acting, understand the state of the world with the "Context
Orientation" sequence below: `tw-flow status` when anchored, `tw-flow ponder`
when not.

### Phase 2: Create Plan
Break down a goal into a dependency chain.
```bash
tw-flow plan feature-x
  "DESIGN|Design API schema|research"
  "EXECUTE|Implement logic|implementation"
```

### Phase 3: Execute (Act)
Pick the top task and work.
```bash
tw-flow execute <uuid>
```
**CRITICAL:** This command triggers the **Context Briefing**. You MUST read and acknowledge any `══ INHERITED CONTEXT ══` displayed.

### Phase 4: Context (Record)
Document your work as you go. Use `tw-flow note` for mid-task decisions and `tw-flow outcome` for final results.
```bash
tw-flow note <uuid> decision "Using library Y."
```

### Phase 5: Review (Verify)
**CRITICAL:** Never close a task silently.
1.  **Linting & Quality**: Ensure all code passes the project's quality gates.
2.  **Documentation Gate**: If the change affects user-facing behavior or resolves a documented finding, update the relevant documentation before recording the outcome. If no doc change is needed, record why in the task context.
3.  **Summary**: Summarize the work performed.
4.  **Demonstration**: Show the result (code, file, output, tests).
5.  **Consent**: Ask: "Shall I close this?" Inside an approved E2E initiative (`E2E AUTONOMY` in `tw-flow status`) the approval is the consent: record the outcome and close without asking.

### Phase 6: Outcome (Capture)
Upon user approval ("looks good", "yes"), you **MUST** record the final result.
```bash
tw-flow outcome <uuid> "Created file X and updated Y."
```

### Phase 7: Close (Finalize)
Only after recording the outcome.
```bash
tw-flow done <uuid>
```
`done` moves the focus to the plan's next ready task by itself; re-read `tw-flow focus` and re-anchor to the next pending task in the same plan only if it did not. If the plan has no pending tasks, clear the focus. Never leave next-task resolution to the global urgency heap.
