# Jacazul Launcher (Monstro do Lago) 🐊

**Stop AI Amnesia. Master Your Workflow.**

Jacazul Launcher is a high-performance, dual-mode environment designed to run AI-powered command line tools (Gemini, Opencode, Copilot, Claude) with persistent memory, structured task management, and distinct personalities.

## 🌟 Why Jacazul?

Most AI interactions are transient. You lose context, plans get messy, and results are hard to reproduce. Jacazul solves this by providing:

- **🧠 Persistent Tactical Memory**: Isolated Taskwarrior databases per project. Your AI never forgets what it was doing.
- **🛡️ Dual-Mode Security**: Run in isolated containers (**CAGED**) for maximum safety or native host (**COUNSELOR**) for raw performance.
- **🎭 Multi-Persona System**: Switch between distinct AI characters to match your current workflow vibe.
- **🚀 7-Phase Lifecycle**: A robust workflow (Orient, Plan, Execute, Context, Review, Outcome, Close) that ensures high-integrity delivery.

---

## 🎭 Meet the Navigators

You don't just work with an AI; you work with a partner. Swapping is conversational—no special commands required. Just ask for them by name: *"me traz a codana"*, *"bring me Arnalbam"*, or *"chama o jacazul"*.

| Navigator | Style | Best For... |
| :--- | :--- | :--- |
| **🐊 Jacazul** | PT-BR, Street-smart, Laid-back. | Project orientation and quick navigation. |
| **{🔷} Codana** | EN, Tactical, Professional, Sharp. | Complex implementations and exactness. |
| **{💪} Arnalbam** | Bilingual, High-octane, Gym-themed. | Motivation, heavy refactoring, and "shredding" code. |
| **🦉 Atena** | Pedagogical, Wise, Encouraging. | Learning new workflows and step-by-step guidance. |

For detailed persona guides, persistent anchors, handoffs, and session refresh behavior, see the **[Persona Switching Guide](docs/agents/persona-switching.md)** and **[Documentation Central](docs/README.md)**.

---

## 🚀 Getting Started

### 1. Pre-requisites
- **Python 3.13+**
- **Go** (for security modules)
- **Taskwarrior** (2.6+ or 3.x)
- **GitHub CLI (gh)**

### 2. Quick Install
```bash
make configure
make github
```

### 3. Run Your Engine
```bash
jacazul-gemini      # Gemini CLI
jacazul-claude      # Claude CLI
jacazul-opencode    # Opencode CLI
jacazul-copilot     # Copilot CLI
jacazul-pi          # Pi CLI with Jacazul footer/dashboard integration
```

For Pi footer/dashboard behavior, see [pi-jacazul-line](docs/pi-jacazul-line.md).
For OpenCode TUI behavior, see [opencode-jacazul-line](docs/opencode-jacazul-line.md).

### 4. Generate Prompt Targets

When you need to regenerate prompt artifacts manually, choose the target at
runtime:

```bash
jacazul-hatch --target pi       # shared engine consumed by Pi
jacazul-hatch --target openai    # shared engine for an OpenAI integration
jacazul-hatch --target all       # engine once plus supported adapters
```

`--client` remains a compatibility alias for `--target`. The shared engine is
always generated once; only clients with a native agent format receive an
adapter artifact.

### 5. The First Set (Conversational Flow)

Jacazul tools are designed for natural interaction. You provide the intent; your Navigator handles the CLI.

| You Say... | Your Navigator Runs... |
| :--- | :--- |
| "onboard" or "full status" | `tw-flow ponder` (Strategic View) |
| "status" or "o que estamos fazendo?" | `tw-flow status` (Tactical View) |
| "create a plan X with tasks A and B" | `tw-flow plan X "A" "B"` |
| "focus on this" or "foca nessa task" | `tw-flow focus ind task <uuid>` |
| "start task <uuid>" | `tw-flow execute <uuid>` |
| "me traz a codana" | `jacazul-persona codama` |
| "bring me arnalbam" | `jacazul-persona arnalbam` |
| "chama a atena" | `jacazul-persona atena` |

---

## 🌟 Interaction Philosophy: NO BULLSHIT

We follow a strict **NO BULLSHIT** policy. Your navigators won't give you fake praise or fluff. 
- **Genuine Feedback:** If a technical approach is weak, they'll say it. 
- **Collaborative by Default:** **COUNSELOR** is not read-only; it is guided collaboration with explicit confirmation for high-impact actions.
- **Direct Action:** Task-level **[EXECUTE]** means the agent directly edits project files; high-autonomy environment modes like **UNHINGED** reduce friction for trusted repairs.
- **Conversational Switching:** No special syntax. Just ask for your preferred partner by name.

---

## 🏗️ Deep Dive

For technical details, internal architecture, and file layouts, see [Technical Architecture](docs/ARCHITECTURE.md).

## 🛠️ Expert Skills

Jacazul extends your capabilities via specialized skills:
- **Taskwarrior Expert**: Advanced workflow persistence.
- **Python Expert**: Legacy, greenfield and migration modes, PEP 8 with the explicit 79-column preference, review on the shared scale.
- **Python Tutor**: Adaptive Python learning on the tutor core, including legacy reading and modernization.
- **JS/TS Expert**: Framework-neutral JavaScript and TypeScript in legacy, greenfield and migration modes; keeps JavaScript thin at the edge unless you choose full-stack.
- **Zig Expert**: Explicit, allocator-honest, safety-aware Zig pinned to the installed release (verified on 0.16).
- **Zig Tutor**: Adaptive Zig learning on the tutor core; every example compiled on your toolchain.
- **PHP Expert**: PHP as a language from 5.x legacy to modern 8.x, framework-neutral, with a census-driven 5.6 to 8.x migration method and a production-floor guard.
- **PHP Tutor**: Adaptive PHP learning on the tutor core, including legacy reading and the migration path.
- **Shell Expert**: POSIX sh and bash with dialect detection (sh-mode), a pitfall census (sh-census), honest set -e rules and idempotent setup scripts.
- **Shell Tutor**: Adaptive shell learning on the tutor core; every example parsed and run on your target shell.
- **JS/TS Tutor**: Adaptive JavaScript and TypeScript learning on the tutor core, platform first, the backend boundary decided once.
- **Go Expert**: Idiomatic Go, gofmt-to-goimports formatting, and Line of Sight readability.
- **UI Expert**: UI verified in a real browser with computed values instead of screenshots; browsers launched, never attached, the same way in every harness; `jacazul ui doctor` audits what is running.
- **Rust Expert**: Idiomatic Rust engineering, ownership, safety, async, and quality gates.
- **Rust Tutor**: Adaptive Rust learning with learner calibration and progressive curriculum.
- **Go Tutor**: Adaptive Go learning on the same tutor core, paired with the Go Expert.
- **Tutor Core**: Shared teaching contract; a tutor decides how to teach, its expert decides what is true.
- **Code Review**: One finding scale (level, advisory, area, evidence) shared by every language expert.
- **Git Expert**: Conventional commits with no AI attribution, workflow detection and pinning (git-mode) for linear or merge teams, a pre-push commit census (git-census) and non-interactive history recipes.
- **GitHub Broker**: Secure, credential-less ticket synchronization.

---

## 📝 License

MIT

**Philosophy:** "Plan effectively, execute efficiently, and never lose context."
