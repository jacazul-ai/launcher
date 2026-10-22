# Documentation Central 📚

Welcome to the Jacazul Launcher documentation. This project is built around the concept of **Persistent Tactical Memory** and **Multi-Persona Navigation**.

## 📖 Table of Contents

### 🚀 Getting Started
- [Quick Start Guide](getting-started.md) - Host and Sandbox setup.
- [Verification Methodology](verification-methodology.md) - How we ensure high-integrity delivery.
- [Technical Architecture](ARCHITECTURE.md) - Internal structure and CLI reference.

### 🎭 The Navigators (Personas)
- [Multi-Persona System](agents/persona-system.md) - Architecture and design.
- [Jacazul & Codana](agents/README.md) - The original duo.
- [Arnalbam & Atena](agents/README.md) - The Shredded and the Wise additions.
- [Persona Switching](agents/persona-switching.md) - How to swap partners mid-session.

### 🛠️ Expert Skills
- [Taskwarrior Expert](taskwarrior-expert.md) - Mastering the 7-phase workflow.
- [Interaction Modes](interaction-modes.md) - DESIGN/GUIDE/REVIEW/EXECUTE collaboration semantics.
- [Python Expert](python-expert.md) - Legacy, greenfield and migration modes, py-mode, py-check and PEP 8.
- [JS/TS Expert](js-ts-expert.md) - Framework-neutral JavaScript and TypeScript, js-mode, js-check, thin edge or full-stack by your choice.
- [Zig Expert](zig-expert.md) - Version-pinned Zig, allocators and errdefer, safety modes, std.Io, review on the shared scale.
- [PHP Expert](php-expert.md) - PHP as a language, php-mode, php-census, the two-pin 5.6 to 8.x migration method.
- [Shell Expert](bash-expert.md) - POSIX sh and bash, sh-mode, sh-census, set -e truth table, portability and idempotence.
- [Git Expert](git-expert.md) - Commit standards, git-mode workflow pin and detection, git-census before push, non-interactive rebase recipes.
- [Go Expert](go-expert.md) - Idiomatic Go, gofmt-to-goimports formatting, and Line of Sight readability.
- [UI Expert](ui-expert.md) - UI verified in a real browser with computed values, browsers launched never attached, `jacazul ui doctor`.
- [Tutors](tutor.md) - Learning a language with a tutor paired to its expert.
- [Skill Authoring Methodology](skill-methodology.md) - Subject-agnostic rules for writing and maintaining any skill: descriptions, bodies, reference-vs-skill, cross-references, evaluation.
- [Skill Evals](skill-evals.md) - Running a skill's eval suite, grading what the agent did, reading traces, and the current jacazul-engine and ui-expert records.
- [Skills Index](skills/README.md) - Every skill, including Rust Expert, Rust Tutor, Go Tutor, and the shared Code Review scale.
- [GitHub Broker](github-broker.md) - Secure issue and ticket synchronization.

### 🔒 Advanced Concepts
- [Environment Modes](environment-modes.md) - COUNSELOR (Safety) vs UNHINGED (Autonomy).
- [Output Caching](tw-flow-cache.md) - Session-scoped context protection.
- [Flow Smoke Check](flow-smoke-check.md) - Dry-run the storage check, see where the flow database lands, prove the Taskwarrior silo is never written.
- [Production Readiness Proposal](proposals/production-readiness.md) - Future risk-based release review across security, correctness, operations, and UX.
- [Go Launcher Proposal](proposals/go-launcher.md) - One `jacazul` binary with a subcommand per harness, replacing the Bash launchers.
- [Agnostic Conversation Window](proposals/agnostic-conversation-window.md) - A shared 50-turn context window with Go adapters for every harness.
- [Broker Project Proposal](proposals/broker.md) - The GitHub broker leaves the launcher for its own project, with Postfix-style privilege separation around the vault.
- [Go Launcher Migration State](proposals/go-launcher-migration.md) - Where each migration step stands, what closes the migration, and what waits for it.
- [Pi Durable Research](research/pi-durable.md) - Evaluates Pi Durable, Cloudflare PiHarness, and a possible Jacazul durable runtime.
- [Personas Proposal](proposals/personas.md) - A persona changes the voice, never the content; on-demand and user-defined personas.
- [EXECUTOR Mode Proposal](proposals/executor-mode.md) - A spawned agent that works a task unattended, replacing UNHINGED.
- [NO BULLSHIT Policy](agents/no-bullshit-policy.md) - Our feedback standard.

---

## 🌟 The Navigator Ecosystem

We use distinct AI personalities to match your workflow needs. Swapping is conversational—no commands required.

| Navigator | Voice | Specialization |
| :--- | :--- | :--- |
| **🐊 Jacazul** | PT-BR | Street-smart orientation and quick wins. |
| **{🔷} Codana** | EN | Tactical precision and complex logic. |
| **{💪} Arnalbam** | Bilingual | High-octane motivation and heavy refactoring. |
| **🦉 Atena** | Pedagogical | Step-by-step guidance and workflow training. |

---

## 🗺️ Documentation Map

Which doc to update when a change is user-facing (the Documentation Mandate
in `AGENTS.md`):

| File | Audience | Intent |
|---|---|---|
| `README.md` | New users | Entry point. Trigger-based: "I want to X → do Y". Links to docs for depth. |
| `docs/tw-flow.md` | Users | Trigger-based CLI reference. Every command = a trigger + what it does. |
| `docs/getting-started.md` | New users | First-session walkthrough. Minimal prerequisites → first working command. |
| `docs/taskwarrior-expert.md` | Users | 7-phase workflow from the user's perspective. When to use each phase. |
| `docs/interaction-modes.md` | Users | Mode selection guide. "I want to X → use mode Y." |
| `docs/environment-modes.md` | Users | COUNSELOR vs UNHINGED. When and why to switch. |
| `docs/github-broker.md` | Users | Ticket sync triggers and credential-less flow. |
| `docs/tw-flow-cache.md` | Users | Cache behavior, signals, and bypass triggers. |
| `docs/flow-smoke-check.md` | Users / Contributors | Dry run and sandbox apply of the `jacazul flow` storage check; what each line and failure means. |
| `docs/skill-methodology.md` | Contributors / AI Agents | Subject-agnostic rules for creating and maintaining any skill: descriptions, bodies, reference-vs-skill, cross-references, evaluation. |
| `docs/skill-evals.md` | Contributors / AI Agents | Running a skill's eval suite, writing graders that measure what the agent did, reading traces, comparing before and after a change. |
| `docs/ARCHITECTURE.md` | Contributors | Internal design decisions. Not trigger-based — explains *why*, not *how to use*. |
| `AGENTS.md` | AI Agents | Repository mandates no skill carries, and where the rest lives. |

**Writing rule.** `README.md` and every `docs/` file except ARCHITECTURE
follow the **Trigger → Action** pattern: organized around what the user wants
to accomplish, each section answering "when the user does or wants X, they run
or see Y", with internals linked to `docs/ARCHITECTURE.md` instead of inlined.
`docs/ARCHITECTURE.md` is the only file organized from the system's
perspective: design decisions, boundaries and trade-offs, for contributors and
agents investigating root causes.

---

## 🆘 Troubleshooting & Support

1. Check the **[Technical Architecture](ARCHITECTURE.md)** for CLI parity and path issues.
2. Use the `onboard` trigger to refresh your agent's context.
3. Consult the **[Verification Methodology](verification-methodology.md)** if tasks are failing Quality Gates.

---

**Philosophy:** "Plan effectively, execute efficiently, and never lose context."
