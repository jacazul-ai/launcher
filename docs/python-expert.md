# Python Expert Skill

Guide for the python-expert skill: Python engineering in legacy, greenfield
and migration trees, with the house `py-check` gate and review on the shared
`code-review` scale.

## Trigger → Action

### When you touch any Python tree

Run `py-mode <root>` first. It prints the mode and the evidence behind it:

```text
🐊 PY_MODE: migration (source: scan)
  - floor 3.13 from requires-python
  - modern packaging: pyproject [project] or lockfile
  - legacy code: os.path string surgery x303
  - annotated defs: 168/536
```

| Mode | Meaning | What the expert does |
|---|---|---|
| `legacy` | Python 2 remnants, `setup.py`-only, untyped, old floor | Preserves behavior. No reformat of untouched files, no new tooling, fixes match the surrounding style. |
| `greenfield` | Modern packaging, 3.10+ floor, typed, formatter configured | Applies the full modern baseline. |
| `migration` | Mixed markers | Incremental ordered steps, one commit each, suite green before and after. |

Override the scan with `JACAZUL_PY_MODE=legacy|greenfield|migration` or with
`[tool.jacazul] py_mode = "..."` in `pyproject.toml`. The expert states the
mode in its first Python response and records a decision when you override.

### When you want the migration path for an old codebase

The expert follows the sequence in
[`skills/python-expert/PLAYBOOK.md`](../skills/python-expert/PLAYBOOK.md):
interpreter floor, packaging metadata, formatter (one commit, added to
`.git-blame-ignore-revs`), linter, typing at boundaries, test runner,
dependencies, idiom sweep. A step that changes behavior is a bug, not a
step.

### When you ask for a Python code review

Findings use the shared [`code-review` scale](../skills/code-review/SKILL.md)
(level, advisory, area, evidence) with the Python scenarios in
[`skills/python-expert/CODE-REVIEW.md`](../skills/python-expert/CODE-REVIEW.md).
The mode changes what counts: a modern idiom dropped into a legacy module is
a finding against the change; a migration commit that hides a behavior
change is `WARNING` / `FIX-NOW`.

### When you run the gate

```bash
py-check <path>            # greenfield and migration: format, fix, validate
py-check --check <path>    # legacy or review: validate only, writes nothing
py-check --all <path>      # every pycodestyle violation, not one per code
py-check --gate <path>     # syntax and PEP 8 only, writes nothing
```

`py-check` refuses to run without a path, so it never reformats the whole
repository by accident. Without `--check` it writes: `ruff format`, then
`ruff check --fix`, then validation with `ruff check` and `pycodestyle`.

`tw-flow done` runs `--gate` on every modified or untracked Python file
before it closes a task. The gate blocks only a syntax error or a PEP 8
violation; the modernization findings of `ruff check` (such as `Optional`
instead of `X | None`) never block a close, so closing a task never forces a
sweep of a file nobody asked to modernize.

The banner says what it resolved:

```text
🐊 py-check: mode migration (scan), line length 79 (pyproject.toml, house preference 79), writing
```

### When the line length is not 79

The house preference is 79 and stays explicit. Resolution order:
`--line-length`, `JACAZUL_PY_LINE_LENGTH`, the project's own configuration
(`[tool.ruff]`, `[tool.black]`, `[flake8]`/`[pycodestyle]`
`max-line-length`, `.editorconfig`), then 79. A greenfield tree that
declares nothing gets a prompt to write `line-length = 79` under
`[tool.ruff]`.

### When you must not reformat a legacy tree

Set `JACAZUL_PY_IGNORE_FORMATTING=1`, or rely on the guard: a legacy tree
with no formatter configuration runs check-only automatically. The banner
says `check-only` and explains why.

### When py-check shows one violation per code

It calls `pycodestyle --first` by default. One `E501` means at least one
long line. Re-run until it passes, or use `--all`.

### When the formatter cannot fix a long line

`ruff format` never breaks a string literal. Every `E501` inside a
docstring, comment, or string is a manual fix: wrap the text across lines
and keep the wording. Do not split a string into implicitly concatenated
parts; the formatter rejoins them when the merged line fits.

```python
# Undone by the next py-check run: the parts fit on one line when merged.
msg = ("Standardization: tw-flow plan must not add default "
       "due/priority.")

# Survives: the docstring text is wrapped, not concatenated.
def test_cool_down(self):
    """Standardization: 'tw-flow plan' must not add default
    due/priority and must support hyphens (Fix #37).
    """
```

### When tests must vary the environment before import

Values read at import time or cached in `functools.cache` cannot be changed
by `monkeypatch`. Run the case in a child process with `sys.executable`, a
guard variable, a narrow test filter, an explicit environment and a
timeout; read the first line of its output. See the
[playbook](../skills/python-expert/PLAYBOOK.md#process-isolated-tests-for-import-time-environment).

### When you want to learn Python

Ask for a tutorial. The engine activates `tutor`, `python-tutor` and
`python-expert` together; see [Tutors](tutor.md).

## The Python Policy Sentinel

`scripts/python` wraps the interpreter and prints the JACAZUL PYTHON POLICY
ALERT banner on every invocation. Silence it with `--skill-activated`, which
the wrapper consumes before handing the remaining arguments to Python:

```bash
python --skill-activated script.py
```

The flag belongs to that wrapper only; `py-check` has its own parser and
rejects it.

## Best Practices

1. Name the mode before the first edit.
2. Scope `py-check` to the file or directory you changed.
3. In legacy trees, use `--check` and match the local style.
4. Migrate in separate commits; never mix a step with a behavior change.
5. Trust the formatter for code, never for strings.

---

**Version:** 2.0.0
**Last Updated:** 2026-09-13
