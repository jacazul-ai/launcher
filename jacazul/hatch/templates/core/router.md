## 🧭 Reference Router

The triggered protocols live in `references/`, next to this file. When a
trigger below fires, read the reference before acting; it holds the full
procedure. Every reference is one read, with no further references inside.

| Trigger | Read |
|---|---|
| Presenting the output of an `onboard`, `cuida`, `rala`, `avia`, `atividade`, status, ponder, roadmap or project-overview request | `references/onboard.md`, read as its own call next to the commands; what to run is "Context Orientation" below |
| A pending session note, `tw-flow session resume`, a handoff question; dump phrases ("dá um dump", "salva o estado", "vou fechar", "contexto tá zoado", "freeze state", "lost track") | `references/session.md` |
| A `[GUIDE]` task or request; naming a mode in the user's language (MODE vs modo) | `references/modes.md` |
| The session language is not anchored yet, or the user keeps writing in another language | `references/language.md` |
| Another agent or session continuing this work; a consensus review (`consensus review`, `revc`, `crev`, "manda um consensus") | `references/collaboration.md` |
| A request, in any language, to develop, implement, finish or take care of something end to end ("desenvolve isso e2e", "take care of this e2e"), the operator's approval of that contract ("pode implementar E2E"), or `E2E AUTONOMY` in `tw-flow status`; not `e2e` alone or end-to-end tests | `references/e2e-development.md` |
| `i&d`, `ied`, or any other shorthand not defined in this hub | `references/glossary.md` |
| A persona handoff | `references/personas/<id>.md` from the Persona Roster |
| A `tw-flow`, `ponder`, broker, hatch or persona command you need the syntax for | `references/onboard.md` (CLI Quick Reference) |

Three triggers act before any read:

- **Orientation** (`onboard`, `cuida`, `rala`, `avia`, `atividade`, status,
  ponder): run the "Context Orientation" sequence of this hub right away;
  `references/onboard.md` only shapes how its output is presented.
- **Focus anchoring** ("foca nisso", "focus on this"): run
  `tw-flow focus ind task <uuid>` as the first action, then continue.
- **Immediate dump** ("dá um dump", "congela o estado", "restart session",
  "contexto tá zoado", "lost track"): run `tw-flow session dump` first, then
  read `references/session.md` to fill in the note.
