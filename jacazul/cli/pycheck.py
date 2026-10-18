#!/usr/bin/env python
"""py-check: house Python gate with Error-as-Prompt feedback.

Phases: ruff format (writes), ruff check --fix (writes), ruff check,
pycodestyle. ``--check`` and the ignore guard skip the writing phases.
``--gate`` is what ``tw-flow done`` runs: syntax and pycodestyle only,
never writing, so closing a task never forces a modernization sweep.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from jacazul.pyexpert.archaeology import resolve_mode
from jacazul.pyexpert.formatting import (
    HOUSE_LINE_LENGTH,
    ignore_formatting,
    resolve_line_length,
)

# 🐊 Jacazul py-check (v2.0.0)

PROMPTS = {
    "E302": "Missing blank lines between functions. Fix: Add 2 blank lines.",
    "E501": "Line too long. Fix: Wrap the line at the resolved line length.",
    "W291": "Trailing whitespace. Fix: Remove extra spaces at end of line.",
    "E401": "Multiple imports on one line. Fix: Split into individual lines.",
    "E305": (
        "Expected 2 blank lines after class/function. Fix: Add 2 blank lines."
    ),
    "E306": (
        "Expected 1 blank line before a nested definition. "
        "Fix: Add 1 blank line."
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="py-check",
        description="Format, fix and validate Python with tactical prompts.",
    )
    parser.add_argument("path", nargs="?", help="file or directory to check")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate only; never write to disk",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="syntax and PEP 8 only, never writing (the tw-flow done gate)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="print every pycodestyle violation instead of one per code",
    )
    parser.add_argument(
        "--line-length", type=int, help="override the resolved line length"
    )
    parser.add_argument(
        "--mode",
        choices=("legacy", "greenfield", "migration"),
        help="override the resolved mode",
    )
    return parser


def _project_root(target: Path) -> Path:
    start = target if target.is_dir() else target.parent
    for candidate in (start, *start.parents):
        for marker in ("pyproject.toml", "setup.py", "setup.cfg", ".git"):
            if (candidate / marker).exists():
                return candidate
    return start


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def run_beautifier(target: str, line_length: int) -> None:
    print(f"🐊 Beautifying {target} via 'ruff format'...")
    _run(["ruff", "format", f"--line-length={line_length}", target])


def run_ruff(target: str, line_length: int, write: bool) -> bool:
    print("🐊 Running ruff logic check...")
    if write:
        _run(
            ["ruff", "check", "--fix", f"--line-length={line_length}", target]
        )
    res = _run(["ruff", "check", f"--line-length={line_length}", target])
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        return False
    return True


def run_format_check(target: str, line_length: int) -> bool:
    print("🐊 Running ruff format --check (check-only, nothing written)...")
    res = _run(
        ["ruff", "format", "--check", f"--line-length={line_length}", target]
    )
    if res.returncode != 0:
        print(res.stdout)
        print(
            "💡 PROMPT: formatting differs from the resolved style. "
            "Run py-check without --check when the mode allows writing.",
            file=sys.stderr,
        )
        return False
    return True


def run_syntax_check(target: Path) -> bool:
    print("🐊 Running syntax check...")
    files = sorted(target.rglob("*.py")) if target.is_dir() else [target]
    ok = True
    for path in files:
        try:
            compile(path.read_bytes(), str(path), "exec")
        except SyntaxError as err:
            print(f"{path}:{err.lineno}: SyntaxError: {err.msg}")
            ok = False
    return ok


def run_pycodestyle(target: str, line_length: int, show_all: bool) -> bool:
    print("🐊 Running pycodestyle final validation...")
    cmd = ["pycodestyle", f"--max-line-length={line_length}"]
    if not show_all:
        cmd.append("--first")
    res = _run([*cmd, target])
    if res.returncode == 0:
        return True

    output = res.stdout.strip()
    print(output)
    found = [
        f"💡 PROMPT [{code}]: {prompt}"
        for code, prompt in PROMPTS.items()
        if code in output
    ]
    if found:
        print("\n" + "\n".join(found), file=sys.stderr)
    else:
        print(
            "\n💡 PROMPT: Linter violation detected. "
            "Fix the PEP 8 issue identified above.",
            file=sys.stderr,
        )
    return False


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.path:
        print(
            "❌ py-check needs an explicit path.\n"
            "   ACTION: pass the file or directory you changed "
            "(py-check jacazul/cli/pycheck.py). Running on '.' would "
            "reformat the whole repository.",
            file=sys.stderr,
        )
        return 2

    target = Path(args.path)
    if not target.exists():
        print(f"❌ {target} does not exist.", file=sys.stderr)
        return 2

    root = _project_root(target.resolve())
    if args.gate:
        line_length, length_source = resolve_line_length(
            root, flag=args.line_length
        )
        print(
            f"🐊 py-check gate: syntax and PEP 8, line length {line_length} "
            f"({length_source}), check-only"
        )
        syntax_ok = run_syntax_check(target)
        pycode_ok = run_pycodestyle(str(target), line_length, args.all)
        if not (syntax_ok and pycode_ok):
            print(
                "\n❌ Python validation failed. Fix the syntax or PEP 8 "
                "violations above.",
                file=sys.stderr,
            )
            return 1
        print("\n✅ Python gate passed: syntax and PEP 8 are clean.")
        return 0

    mode, mode_source = (
        (args.mode, "flag") if args.mode else resolve_mode(root)
    )
    line_length, length_source = resolve_line_length(
        root, flag=args.line_length
    )
    write = not args.check and not ignore_formatting(mode, root)

    print(
        f"🐊 py-check: mode {mode} ({mode_source}), "
        f"line length {line_length} ({length_source}, house preference "
        f"{HOUSE_LINE_LENGTH}), {'writing' if write else 'check-only'}"
    )
    if mode == "greenfield" and length_source == "default":
        print(
            f"ℹ Greenfield tree with no declared line length. "
            f"ACTION: declare line-length = {HOUSE_LINE_LENGTH} under "
            "[tool.ruff] in pyproject.toml so the preference is explicit."
        )
    if not write and not args.check:
        print(
            "ℹ Formatting guard active (JACAZUL_PY_IGNORE_FORMATTING or "
            "legacy tree without formatter config). Nothing is written."
        )

    if write:
        run_beautifier(str(target), line_length)
        format_ok = True
    else:
        format_ok = run_format_check(str(target), line_length)

    ruff_ok = run_ruff(str(target), line_length, write)
    pycode_ok = run_pycodestyle(str(target), line_length, args.all)

    if not (format_ok and ruff_ok and pycode_ok):
        print(
            "\n❌ Python validation failed. Follow the prompts above to fix.",
            file=sys.stderr,
        )
        return 1

    print("\n✅ Python validation passed. Logic and Style are clean!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
