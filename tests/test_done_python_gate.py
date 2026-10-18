import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from jacazul.cli.flow import FlowManager

TASK = {
    "uuid": "deadbeef-1234",
    "status": "pending",
    "annotations": [{"description": "OUTCOME: done"}],
}


class DonePythonGateTest(unittest.TestCase):
    """tw-flow done gates modified Python through py-check --gate."""

    def setUp(self):
        self.cwd = os.getcwd()
        self.root = tempfile.mkdtemp(prefix="jacazul_gate_")
        os.chdir(self.root)
        for name in ("a.py", "b.py"):
            with open(name, "w", encoding="utf-8") as f:
                f.write("x = 1\n")
        self.calls = []

    def tearDown(self):
        os.chdir(self.cwd)

    def _done(self, gate):
        def run(cmd, **kwargs):
            if cmd[:2] == ["git", "status"]:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=" M a.py\n?? b.py\n", stderr=""
                )
            self.calls.append(cmd)
            return gate(cmd)

        with (
            patch("jacazul.cli.flow.TaskWrapper"),
            patch("jacazul.cli.flow.FocusManager"),
            patch("jacazul.cli.flow.CacheManager"),
            patch("jacazul.cli.flow.BrokerFactory.get_broker"),
            patch("jacazul.cli.flow.subprocess.run", side_effect=run),
            patch.dict(os.environ, {"JACAZUL_TESTING": "false"}),
            patch("sys.stdout"),
        ):
            flow = FlowManager()
            flow.tw.export.return_value = [TASK]
            flow.tw.run.return_value = MagicMock(returncode=1, stderr="")
            flow.resolve_uuid = MagicMock(return_value=TASK["uuid"])
            flow.focus.advance.return_value = None
            flow.cmd_done("deadbeef")

    def test_gate_runs_once_per_file_through_the_installed_package(self):
        with self.assertRaises(SystemExit):
            # tw.run fails on purpose, so done stops right after the gate.
            self._done(lambda cmd: subprocess.CompletedProcess(cmd, 0))

        gate = [sys.executable, "-m", "jacazul.cli.pycheck", "--gate"]
        self.assertEqual(self.calls, [[*gate, "a.py"], [*gate, "b.py"]])

    def test_a_failing_file_blocks_done(self):
        with (
            patch("sys.stderr") as err,
            self.assertRaises(SystemExit),
        ):
            self._done(lambda cmd: subprocess.CompletedProcess(cmd, 1))

        written = "".join(c.args[0] for c in err.write.call_args_list)
        self.assertIn("Python validation failed", written)
        self.assertIn("ACTION:", written)

    def test_a_missing_gate_is_an_instructional_error(self):
        def missing(cmd):
            raise FileNotFoundError(cmd[0])

        with (
            patch("sys.stderr") as err,
            self.assertRaises(SystemExit),
        ):
            self._done(missing)

        written = "".join(c.args[0] for c in err.write.call_args_list)
        self.assertIn("ACTION:", written)
        self.assertNotIn("Traceback", written)


if __name__ == "__main__":
    unittest.main()
