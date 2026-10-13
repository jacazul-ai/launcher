## 🔁 E2E Development

```text
OPEN -> UNDERSTAND -> CLOSE THE CONTRACT -> APPROVAL -> IMPLEMENT E2E
-> VALIDATE -> DEMONSTRATE -> REVIEW THE TRAIL -> CLOSE
```

How the agent develops an initiative: close every detail first, wait for
the operator's explicit approval, then implement end to end while
controlling focus, isolation, validation and history. The procedure names
no language or project; the gates come from what is being implemented.

It applies when the operator asks, in any language, to develop, implement,
finish or take care of something end to end. `e2e` alone, or a request
about end-to-end tests, is not this procedure.

## 1. Open the Work

- Create an initiative with dependent tasks: `DESIGN`, `EXECUTE`, `TEST`,
  `REFINE`. Each description names its deliverable, not the workflow.
- Create or link the external ticket on every task.
- Anchor focus on the first task.

## 2. Understand and Close the Contract

Investigate before writing code:

- current behavior and its source of truth;
- scope limits and what stays explicitly out;
- migration and compatibility risks;
- expected output;
- project and session isolation.

When the contract has gaps, ask targeted questions until it is closed;
never implement on a guess. Record in the DESIGN task: the decision,
assumptions, expected behavior, rejected paths and acceptance criteria.
Notes describe this deliverable, never the workflow itself.

## 3. Approval

The operator approves the closed contract, in words like:

> Entendi o contrato, pode implementar E2E.

Without explicit approval nothing is implemented. Anchoring focus on a task
is not approval. Record the approval and the contract as the DESIGN
task's `OUTCOME`, close it, and anchor the next task.

**Autonomy:** the approval is the operator's consent for the whole run of
this initiative, so the per-step confirmations of COUNSELOR do not apply
inside it:

1. **Commits:** commit each task's work through `git-expert`
   without asking per commit.
2. **Task closing:** record the `OUTCOME` and run `done`
   without asking "Shall I close this?".
3. **Focus:** anchor the next task of the initiative, and clear the focus
   when the last one is done.

The autonomy never includes a push, a history rewrite, work outside the
approved initiative, or filling a design gap; those still go to the
operator.

## 4. Implement E2E, One Task at a Time

For each task of the initiative:

1. **RED:** write the contract test first and watch it fail. Test the
   whole boundary, not one internal function: success, actionable errors,
   isolation and persistence. Run in an isolated runtime: temporary
   directories, fake binaries at process boundaries, no real user state.
2. **GREEN:** change the sources until the test passes. Generated
   artifacts are never edited; change their sources and regenerate.
3. **REFACTOR**, then a mutation check when viable (break the code, see
   the test fail) and a parity review against the behavior it replaces.
4. **Language gate:** the quality gate of the active language expert.
5. **Atomic commits** through `git-expert`: one logical change per commit,
   selective staging, never `git add .`; feature, docs and refactor never
   mixed; `Refs:` on intermediate commits, `Fixes:` on the commit that
   closes the ticket. Atomicity is what makes that autonomy safe: each
   commit is one change the operator can review, revert, bisect or drop
   on its own in the trail review. A commit that mixes two changes cannot
   be undone without undoing both.
6. **Close the task:** record `OUTCOME`, run `done`, re-read focus and
   re-anchor the next task of the same initiative. Never let the next task
   come from the global urgency heap.

Design is not invented during implementation. A gap found here goes back
to the operator as a question.

## 5. Validate

Run the gates that match what was implemented:

- the active language expert's gate;
- the project's test entry point, as its mandates name it;
- `git diff --check` and `git-census` from `git-expert`.

Report only observed results. A failure that predates the work is named
as such, with evidence, and handed to its own task.

## 6. Demonstrate

Show the operator:

- files changed;
- behavior implemented;
- tests run and their results;
- commits created;
- ticket state;
- current focus.

## 7. Review the Trail

List the initiative's commits and ask the operator to choose:

- **Keep and push:** the trail stays as it is and is pushed once the
  operator authorizes the push.
- **Edit the trail first:** fixup, squash, drop, reword or reorder through
  `git-expert`, with a backup ref before the rewrite and `range-diff`
  after it; then ask again before pushing.

Nothing is pushed without explicit authorization.

## 8. Close

When the last task is done, clear the focus or explicitly anchor the next
initiative.

## The Agreement

First we close the thinking; then the operator approves; then the agent
implements E2E, controlling focus, isolation, validation and history.
