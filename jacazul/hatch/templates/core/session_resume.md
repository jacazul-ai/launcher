## 🔄 Session Resume & Handoff

### Receiving Context (On Restart)

When the opening prompt carries a `📋 Session Handoff` section, the bootstrap
has delivered this session's pending note: run `tw-flow focus`, run
`tw-flow session ack`, and continue from the handoff's next action. The note
keeps arriving at every launch until it is acknowledged.

When `tw-flow status` shows `📋 SESSION NOTE PENDING`, a handoff note from a previous session is waiting. This is **part of the anchored session context** — not optional extra info.

**Protocol (mandatory when banner is present):**
1. Run `tw-flow session resume` — prints the full handoff note
2. Read it entirely — it is the narrative lens that explains the current state
3. Run `tw-flow context <uuid>` — inherited intelligence from Taskwarrior
4. Run `tw-flow session ack` — dismisses the banner, marks note as read
5. Only then proceed with `tw-flow status`

**CRITICAL:** Do not skip reading the output of `tw-flow session resume`. It contains what no task annotation captures: where execution stopped, non-obvious state, and the next concrete action.

The `acknowledged:` marker is written only after the agent reads the
handoff and runs `tw-flow session ack`; it is the only state the note keeps.

**Terminal-first display rule:** Session handoff content is internal during ordinary prompts. For explicit onboard, handoff, full context, resume details, status, or debug trace requests, apply the visibility contract below and report the relevant operational context.

## HANDOFF VISIBILITY CONTRACT

When a session handoff exists, whether `tw-flow session resume` prints it or
the opening prompt carries it, the agent MUST:

1. Read it completely before taking any other action.
2. Treat it as mandatory operational context.
3. In the next user-facing response for an explicit onboarding request,
   summarize:
   - focused plan and task;
   - relevant decisions, research, and outcomes;
   - current repository and work state;
   - blockers and risks;
   - concrete next actions.
4. Never say only `context loaded`, `handoff acknowledged`, or an equivalent
   confirmation without the operational summary.
5. When the user asks about onboarding, handoff, resume, or status, show all
   relevant operational context, not merely a confirmation.
6. Keep secrets, credentials, host details, and private lab evidence hidden.

A casual greeting does not trigger onboarding. Any follow-up asking whether
onboarding or handoff was read immediately triggers this visibility contract.

### Preparing Context (Before Closing)

**TRIGGER PHRASES — Propose dump (ask first):**
- PT-BR: "vou fechar", "fechando aqui", "to indo", "até mais"
- EN: "closing", "wrapping up", "i'm out", "see you later"

→ Ask: "Quer que eu gere o session dump antes de fechar?"

**TRIGGER PHRASES — Execute dump immediately (no confirmation needed):**
- PT-BR: "dá um dump", "congela o estado", "salva o estado", "bora reiniciar", "reinicia a sessão"
- EN: "do a dump", "freeze state", "save state", "restart session"

**TRIGGER PHRASES — Execute dump immediately (context degradation — agent saves the session):**
- PT-BR: "contexto tá zoado", "tá confuso", "perdeu o fio"
- EN: "lost track", "context is messed up", "i'm confused"

→ For context degradation: run dump immediately, then inform: "Contexto salvo. Recomendo reiniciar com: `jacazul-<agent> --jacazul-session {SESSION_ID}`"

**Protocol (after trigger):**
1. Run `tw-flow session dump` — generates `session-note-{SESSION_ID}.md`
2. Fill in the `<!-- FILL IN -->` section: what was done, what is not obvious, next action
3. Inform the user: "Dump gerado. Resume com: `jacazul-<agent> --jacazul-session {SESSION_ID}`"

### File Behavior for dump (Error as Prompt)

- **First call:** Creates the file with `<!-- FILL IN -->`. Fill it in now.
- **File exists + `<!-- FILL IN -->` present:** You already ran dump — fill it in, do not regenerate.
- **File exists + no `<!-- FILL IN -->`:** A previous agent filled this. READ IT FIRST.
- **`--force` flag:** Overwrite unconditionally. Use only when explicitly requested.
