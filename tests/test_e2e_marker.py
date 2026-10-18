import orjson

from .base import JacazulTest


class E2EMarkerTest(JacazulTest):
    """An approved E2E plan carries its autonomy in the workflow state."""

    def setUp(self):
        super().setUp()
        self.env["JACAZUL_TESTING"] = "true"
        self.run_cmd(
            f"{self.tw_flow} plan chain 'DESIGN|Design it|r' "
            "'EXECUTE|Build it|i'"
        )
        self.run_cmd(f"{self.tw_flow} plan other 'EXECUTE|Elsewhere|i'")

    def _tags(self, project):
        out, _, _ = self.run_cmd(f"{self.taskp} project:{project} export")
        return {t["description"]: t.get("tags", []) for t in orjson.loads(out)}

    def _focus_first(self, project):
        out, _, _ = self.run_cmd(f"{self.taskp} project:{project} export")
        uuid = min(orjson.loads(out), key=lambda t: t["id"])["uuid"]
        self.run_cmd(f"{self.tw_flow} focus task {uuid}")

    def test_e2e_tags_only_the_plan_pending_tasks(self):
        out, _, code = self.run_cmd(f"{self.tw_flow} e2e chain")

        self.assertEqual(code, 0)
        self.assertIn("E2E AUTONOMY", out)
        for tags in self._tags("chain").values():
            self.assertIn("e2e", tags)
        for tags in self._tags("other").values():
            self.assertNotIn("e2e", tags)

    def test_e2e_rejects_a_plan_without_pending_tasks(self):
        _, err, code = self.run_cmd(f"{self.tw_flow} e2e missing")

        self.assertNotEqual(code, 0)
        self.assertIn("ACTION:", err)

    def test_status_shows_the_autonomy_of_an_e2e_plan(self):
        self.run_cmd(f"{self.tw_flow} e2e chain")
        self._focus_first("chain")

        out, _, _ = self.run_cmd(f"{self.tw_flow} status chain --force")

        self.assertIn("E2E AUTONOMY", out)
        self.assertIn("push", out)
        self.assertNotIn("RESTRICTION: User confirmation required", out)

    def test_status_keeps_the_restriction_outside_e2e(self):
        self._focus_first("other")

        out, _, _ = self.run_cmd(f"{self.tw_flow} status other --force")

        self.assertIn("RESTRICTION: User confirmation required", out)
        self.assertNotIn("E2E AUTONOMY", out)
