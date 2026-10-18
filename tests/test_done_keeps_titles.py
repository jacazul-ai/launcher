import os
import stat
import sys

import orjson

from .base import JacazulTest

FAKE_GH = """#!/bin/sh
# Answers every 'gh issue view' as a CLOSED issue; no network.
echo '{"state": "CLOSED", "title": "Closed upstream"}'
"""


class DoneKeepsTitlesTest(JacazulTest):
    """Closing a ticket-linked task never rewrites a task title (#88)."""

    def setUp(self):
        super().setUp()
        bin_dir = os.path.join(self.test_dir, "bin")
        os.makedirs(bin_dir)
        self._script(os.path.join(bin_dir, "gh"), FAKE_GH)
        self._script(
            os.path.join(bin_dir, "jacazul-broker"),
            f'#!/bin/sh\nexec "{sys.executable}" -c '
            '"import sys; from jacazul.cli.broker import main; '
            'sys.argv[0] = \'jacazul-broker\'; main()" "$@"\n',
        )
        self.env["PATH"] = f"{bin_dir}:{self.env['PATH']}"
        self.env["JACAZUL_TESTING"] = "true"

    @staticmethod
    def _script(path, body):
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def _tasks(self):
        out, _, _ = self.run_cmd(f"{self.taskp} project:linked export")
        return {t["uuid"]: t for t in orjson.loads(out)}

    def test_done_on_a_closed_ticket_keeps_every_title(self):
        self.run_cmd(
            f"{self.tw_flow} plan linked 'EXECUTE|First task|i' "
            "'EXECUTE|Second task|i'"
        )
        before = self._tasks()
        first, second = sorted(before, key=lambda u: before[u]["id"])
        for uuid in (first, second):
            self.run_cmd(f"{self.tw_flow} ticket {uuid} '#88'")
        self.run_cmd(f"{self.tw_flow} outcome {first} finished")

        out, err, _ = self.run_cmd(f"{self.tw_flow} done {first}")

        after = self._tasks()
        self.assertIn("closed locally", out + err)
        self.assertEqual(after[second]["status"], "completed")
        for uuid, task in before.items():
            self.assertEqual(after[uuid]["description"], task["description"])
        notes = [a["description"] for a in after[second]["annotations"]]
        self.assertTrue(
            any(n.startswith("OUTCOME: Automatically closed") for n in notes)
        )
