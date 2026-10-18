import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from jacazul.pyexpert.formatting import (
    ignore_formatting,
    resolve_line_length,
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _write(root, relpath, content=""):
    path = pathlib.Path(root, relpath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestLineLengthResolution(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="jacazul_pyfmt_")

    def test_flag_wins_over_everything(self):
        _write(self.root, "pyproject.toml", "[tool.ruff]\nline-length = 88\n")

        value, source = resolve_line_length(
            self.root, flag=100, env={"JACAZUL_PY_LINE_LENGTH": "120"}
        )

        self.assertEqual((value, source), (100, "flag"))

    def test_env_beats_project_config(self):
        _write(self.root, "pyproject.toml", "[tool.ruff]\nline-length = 88\n")

        value, source = resolve_line_length(
            self.root, flag=None, env={"JACAZUL_PY_LINE_LENGTH": "120"}
        )

        self.assertEqual((value, source), (120, "env"))

    def test_ruff_config_is_read(self):
        _write(self.root, "pyproject.toml", "[tool.ruff]\nline-length = 88\n")

        value, source = resolve_line_length(self.root, flag=None, env={})

        self.assertEqual((value, source), (88, "pyproject.toml"))

    def test_setup_cfg_flake8_is_read(self):
        _write(self.root, "setup.cfg", "[flake8]\nmax-line-length = 100\n")

        value, source = resolve_line_length(self.root, flag=None, env={})

        self.assertEqual((value, source), (100, "setup.cfg"))

    def test_editorconfig_is_read(self):
        _write(
            self.root,
            ".editorconfig",
            "root = true\n\n[*.py]\nmax_line_length = 110\n",
        )

        value, source = resolve_line_length(self.root, flag=None, env={})

        self.assertEqual((value, source), (110, ".editorconfig"))

    def test_house_default_when_nothing_declared(self):
        value, source = resolve_line_length(self.root, flag=None, env={})

        self.assertEqual((value, source), (79, "default"))


class TestIgnoreFormattingGuard(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="jacazul_pyfmt_")

    def test_env_guard_ignores_formatting(self):
        env = {"JACAZUL_PY_IGNORE_FORMATTING": "1"}

        self.assertTrue(ignore_formatting("greenfield", self.root, env=env))

    def test_legacy_without_formatter_config_ignores_formatting(self):
        self.assertTrue(ignore_formatting("legacy", self.root, env={}))

    def test_legacy_with_formatter_config_formats(self):
        _write(self.root, "pyproject.toml", "[tool.black]\nline-length = 88\n")

        self.assertFalse(ignore_formatting("legacy", self.root, env={}))

    def test_greenfield_formats_by_default(self):
        self.assertFalse(ignore_formatting("greenfield", self.root, env={}))


class TestPyCheckCli(unittest.TestCase):
    """Drive the console entry point in a child process."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="jacazul_pycheck_")
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(PROJECT_ROOT)
        self.env.pop("JACAZUL_PY_MODE", None)
        self.env.pop("JACAZUL_PY_IGNORE_FORMATTING", None)

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "jacazul.cli.pycheck", *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_no_path_is_an_error_as_prompt(self):
        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit path", result.stderr.lower())

    def test_check_mode_never_writes(self):
        ugly = _write(self.root, "ugly.py", "x=1\n")

        result = self._run("--check", str(ugly))

        self.assertEqual(ugly.read_text(encoding="utf-8"), "x=1\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("check-only", result.stdout.lower())

    def test_writing_mode_formats_the_file(self):
        _write(
            self.root,
            "pyproject.toml",
            '[project]\nname = "x"\nrequires-python = ">=3.13"\n'
            "[tool.ruff]\nline-length = 79\n",
        )
        ugly = _write(self.root, "ugly.py", "x=1\n")

        result = self._run(str(ugly))

        self.assertEqual(ugly.read_text(encoding="utf-8"), "x = 1\n")
        self.assertEqual(
            result.returncode, 0, msg=result.stdout + result.stderr
        )

    def test_gate_passes_pep8_code_that_is_not_modernized(self):
        # The done gate must not force a modernization sweep: Optional and
        # List are ruff findings, not PEP 8 or syntax errors.
        source = (
            "from typing import List, Optional\n"
            "\n"
            "\n"
            "def f(x: Optional[List[int]]) -> None:\n"
            "    return None\n"
        )
        legacy = _write(self.root, "legacy.py", source)

        result = self._run("--gate", str(legacy))

        self.assertEqual(
            result.returncode, 0, msg=result.stdout + result.stderr
        )
        self.assertEqual(legacy.read_text(encoding="utf-8"), source)
        self.assertIn("gate", result.stdout.lower())

    def test_gate_blocks_a_syntax_error(self):
        broken = _write(self.root, "broken.py", "def broken(:\n    pass\n")

        result = self._run("--gate", str(broken))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python validation failed", result.stderr)
        self.assertIn("broken.py", result.stdout + result.stderr)

    def test_gate_blocks_a_pep8_violation_without_writing(self):
        ugly = _write(self.root, "ugly.py", "x = 1  \n")

        result = self._run("--gate", str(ugly))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("W291", result.stdout)
        self.assertEqual(ugly.read_text(encoding="utf-8"), "x = 1  \n")

    def test_ignore_guard_skips_writing_phases(self):
        ugly = _write(self.root, "ugly.py", "x=1\n")
        self.env["JACAZUL_PY_IGNORE_FORMATTING"] = "1"

        self._run(str(ugly))

        self.assertEqual(ugly.read_text(encoding="utf-8"), "x=1\n")


class TestPyModeCli(unittest.TestCase):
    def test_prints_mode_and_evidence(self):
        root = tempfile.mkdtemp(prefix="jacazul_pymode_cli_")
        _write(root, "setup.py", "import six\n")
        _write(root, "x/__init__.py", "print 'x'\n")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        env.pop("JACAZUL_PY_MODE", None)

        result = subprocess.run(
            [sys.executable, "-m", "jacazul.cli.pymode", root],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("PY_MODE: legacy", result.stdout)


if __name__ == "__main__":
    unittest.main()
