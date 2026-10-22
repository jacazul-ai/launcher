# Skill Evals

How we measure whether a skill changes model behavior, and how to read the
result. The authoring rules for a good case (adversarial, baseline-checked,
judgment over API recall) live in
[`skill-methodology.md`](skill-methodology.md#evaluation); this page covers
running, grading and reading.

The runner is Claude Code's `claude plugin eval`: every run is a Claude Code
session, and the traces, tools and sandbox below are Claude Code's. A result
therefore holds for Claude Code and the model it ran; Gemini, pi, Copilot and
Opencode load skills their own way and are not measured by it. Launching
`claude plugin eval` from pi or another harness does not change that: it is
still a Claude Code measurement. It remains a good bench for the skill text
itself, which every harness loads unchanged, but it does not certify a skill
for pi or Opencode. A runner for another harness keeps its own baseline and
gets its own section once it exists.

## Trigger → Action

### When you want to know if a skill actually helps

Run its suite with a no-skill baseline arm. The harness runs every case
twice: once with the skill installed (`with`) and once without (`without`).
The delta is the skill's effect.

```bash
claude plugin eval skills/<name> --case <case-name> --runs 1 \
  --ablation with-without --no-scaffold --no-publish \
  --max-cost-usd 1 --keep-temp </dev/null
```

| Flag | Why |
|---|---|
| `--case <name>` | One exact case name per call. The filter takes neither `[..]` nor `{..}` globs; loop over names instead. |
| `--runs 1` | Enough to spot a gap. Use more runs before claiming a small delta. |
| `--no-publish` | The default publishes the HTML report. |
| `--max-cost-usd` | Runaway guard. The reported USD is an equivalent figure; on a subscription it is plan usage, not a charge. |
| `--keep-temp` | Keeps each run's `trace.jsonl` so you can see what the agent actually did. |
| `</dev/null` | A backgrounded run otherwise inherits a stdin that never closes, and any prompt inside it hangs forever. |

Run it from the repository root, or pass the skill directory as an absolute
path: the path is resolved against the current directory. Keep the command
on one line when you paste it; a line break ends the command and the flags
after it never reach the eval.

The eval starts its own Claude sessions with `--trust-plugin` and
`--allow-tools Bash`, so an agent's permission guard may refuse to start it.
The command itself runs from any harness through its shell.
When the agent is blocked, the operator runs the same one-line command from
the repository root (in Claude Code, with a `!` prefix so the output lands in
the conversation) and hands the output back.

`--trust-plugin` and `--allow-tools Bash` are the operator's call. Cases that
check shell commands need `--allow-tools Bash`, or the agent cannot even try
them.

### When you write a grader

Grade what the agent *did*, not text that happens to be in the trace.

| Check | Grader | Watch out for |
|---|---|---|
| The agent ran a command | `tool_used`, `tool: Bash`, `input_match` | `input_match` is a regex over the whole serialized input, the Bash `description` included. Anchor it: `'"command":\s*"[^"]*tw-flow focus'`. |
| The agent never ran a command | same, with `min: 0`, `max: 0`, `arm: both` | Without `arm: both` the check does not score under ablation. |
| The agent read a file | `tool_used`, `tool: Read`, `input_match` on the path | Proves loading; it says nothing about obeying the file. |
| The skill fired | `tool_used`, `tool: Skill`, `input_match: <skill>` | Only an indicator under ablation; it does not score. |
| The final reply says or refuses something | `llm` with the default `focus: last_message` | One claim per bullet. An ambiguous bullet fails correct replies. |
| The reply starts with a signature | `regex` over the final message | Fine for fixed text; never regex the trace. |

Two traps cost a full run each before we learned them:

- **Regex over the trace.** A loaded skill quotes command names, so
  `tw-flow focus` matches whether or not the agent ran it.
- **An `llm` judge fed the whole trace.** A trace of about 90 KB made the
  judge vote FAIL on correct runs with no explanation. Point it at the last
  message.

Change a grader only between baselines, never between the two sides of a
comparison.

### When the sandbox cannot run your tool

The eval sandbox hides the operator's home, so `tw-flow` and `taskp` start
and then crash with `ModuleNotFoundError: No module named 'jacazul'`. Grade
the attempt and the reaction: did the agent try the workflow tool first,
report the crash as the blocker, and refuse the raw `task` bypass? Behavior
that only happens *after* a successful call (reading a session note, running
status after focus) stays out of reach until a stub `tw-flow` exists.

### When you need to know whether a reference was read

The hub routes triggers to `references/`. Whether a reference was read shows
only in the trace, so keep the temp dirs and look:

```bash
for d in $(command ls -1dt /tmp/claude-eval-* | head -6); do
  t=$d/out/trace.jsonl
  echo "== $d"
  grep -oE '"skill":"[^"]+"' "$t" | sort -u
  grep -oE '"file_path":"[^"]*references/[^"]*"' "$t" | sort -u
done
```

A healthy run reads exactly the reference its trigger names, and nothing
when nothing triggers. The no-skill arm never reads one. Promote a check you
rely on into a `tool_used` `Read` grader, so the next run proves it without
anyone opening a trace.

Do not run `git` inside a kept directory; the harness seals what the plugin
wrote there.

### When you test whether a skill loads on demand

A case can only load plugins inside the directory under test, so a suite
aimed at one skill cannot see its siblings, and `claude plugin eval skills`
resolves back to the enclosing skill. Build a throwaway plugin that holds
the skills a real session would have, and run the case against it:

```bash
P=$(mktemp -d)/fixture
mkdir -p "$P/.claude-plugin" "$P/skills" "$P/evals"
printf '{"name": "fixture"}\n' > "$P/.claude-plugin/plugin.json"
for s in jacazul-engine taskwarrior-expert git-expert security-expert; do
  rsync -aL --exclude evals skills/$s "$P/skills/"
done
cp -r skills/jacazul-engine/evals/06-commit-loads-git-expert "$P/evals/"
claude plugin eval "$P" --case 06-commit-loads-git-expert --runs 3 \
  --ablation none --no-scaffold --no-publish --max-cost-usd 2 \
  --trust-plugin --allow-tools Bash </dev/null
```

Grade the load with `tool_used` `Skill` `input_match: <skill>` and
`arm: both`, and pair it with a `max: 0` check on a sibling that must stay
unloaded. Use `--runs 3`: a single run cannot tell a flaky trigger from a
missing one. The sandbox also swaps `git` for a null device, so grade that
the skill loaded before the first git command, not that the commit landed.

A skill that never loads almost always has a vague description. Name the
concrete nouns a user would type, as the methodology asks, and re-measure.

### When you compare before and after a change

1. Freeze the graders and record the baseline: cases, flags, model, scores.
2. Make the change.
3. Re-run the same cases with the same flags.
4. Read the `with` column case by case. A drop is a regression even if the
   delta still looks positive, since the `without` arm varies between runs.
5. Record both runs on the task that owns the change.

## Current record: jacazul-engine

Cases in `skills/jacazul-engine/evals/`, `claude-opus-5-5` agent, haiku
judge, graders as of the command-anchored revision. Every column ran with
`--runs 1 --ablation with-without --no-scaffold --no-publish`.

| Column | Engine at | Claude Code | Ran on |
|---|---|---|---|
| Baseline | `4740c75` | 2.1.281 | 2026-09-23 |
| After hub split | `c8cc55f` | 2.1.281 | 2026-09-23 |
| After on-demand experts | `8dab60c` | 2.1.282 | 2026-09-26 |

| Case | Baseline (monolith, 66 KB) | After hub split (33 KB) | After on-demand experts and indexed prompts | Reference read (hub split run) |
|---|---|---|---|---|
| 01 onboard anchors first | 1.00 / 0.00 | 1.00 / 0.33 | 1.00 / 0.00 | `onboard.md`, then `tw-flow focus` |
| 03 status stays on status | 0.75 / 0.25 | 0.75 / 0.50 | 0.75 / 0.25 | `onboard.md` |
| 04 close waits for outcome | 1.00 / 0.67 | 1.00 / 0.67 | 1.00 / 0.67 | none (no trigger) |

Scores are `with / without`. Per-run cost of the `with` arm dropped about 20
percent after the split. "After on-demand experts" is the final re-run after
git-expert and security-expert left the first turn and taskwarrior-expert
was slimmed: the `with` arm held, while first-turn skill bytes fell from
about 95 KB to about 44 KB. The `without` arm moves between runs; with
`--runs 1` treat it as noise. Without a launcher, every `with` run also read
`references/personas/jacazul.md`, the documented fallback voice.

On-demand loading, measured on a four-skill fixture with `--runs 3`:

| Case | Skill expected | Before | After |
|---|---|---|---|
| 06 a commit request | `git-expert` loads before any git command | 3/3 | 3/3 |
| 07 a CI secrets question | `security-expert` loads | 0/3 | 3/3 after its description named concrete triggers |

In both cases the other expert stayed unloaded in every run.

E2E Development trigger, engine at `f92bc86`, Claude Code 2.1.290,
`claude-opus-5-5` agent, run on 2026-10-06 with `--allow-tools
Bash,Edit,Write` so the no-edit graders can fail:

| Case | Runs | With / without | What the `with` arm did |
|---|---|---|---|
| 08 develop end to end, in Spanish | 2 | 1.00 / 0.75 | read `e2e-development.md`, asked for the contract, no Edit or Write |
| 09 run the e2e tests | 1 | 1.00 / 1.00 | never read `e2e-development.md`: tests are not a trigger |
| 10 `cuida disso e2e` | 1 | 1.00 / 0.33 | development, not an onboard; read the reference, no Edit |

Case 08 names the Jacazul workflow like cases 01 to 07: unanchored, the
skill loaded in one of two runs, which measures the description's
auto-triggering rather than the hub routing. The `without` arm also asks
for a contract on its own; the delta is reading and following the
reference.

Not covered yet:

- `session.md`, `modes.md`, `language.md` and `glossary.md` triggers;
- a persona handoff reading another voice and switching signature;
- the real launcher path, where the injected voice should make the persona
  read unnecessary;
- harnesses other than Claude Code;
- case 02 (handoff) and the status call in case 03, which need a stub
  `tw-flow`; case 05 (review routing), which never fires the engine.

## Current record: ui-expert

Cases in `skills/ui-expert/evals/`, `claude-opus-5-5` agent, Claude Code
2.1.306, run on 2026-10-21 with `--ablation with-without --no-scaffold
--no-publish`. A Claude Code measurement only: the skill text is the same
in every harness, but no other harness was measured.

| Case | Runs | With / without | What the `without` arm did |
|---|---|---|---|
| 01 server config next to an open browser | 1 | 1.00 / 0.00 | attached with `--autoConnect` at `@latest`, the incident the skill exists for |
| 02 no server configured | 1 | 1.00 / 0.00 | no pass/fail console snippet |
| 03 screenshot offered as proof | 2 | 1.00 / 0.00 | planned the screenshot as the check, no computed radius |
| 04 jsdom asserting `::before` | 1 | 1.00 / 0.00 | trusted the green jsdom test |

Two graders moved before this baseline. Case 01 first demanded an exact
version number; the `with` arm correctly left a placeholder and the
registry lookup for the operator, so the criterion now accepts an explicit
placeholder and rejects only unpinned or `latest`. Case 03 first hinted
at the joined corners and the baseline passed; it was redesigned without
the hint. A single earlier `with` run of the redesigned case scored 0.00
on a split judge vote (one PASS, two FAIL); the two runs above both
passed.
