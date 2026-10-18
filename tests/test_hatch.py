#!/home/fpiraz/.jacazul-ai/.venv/bin/python
import os
import shutil
import subprocess
import tempfile
import unittest

from jacazul.cli.hatch import build_parser
from jacazul.hatch.engine import hatch_prompt
from jacazul.hatch.persona import PersonaManager


class TestHatchEngine(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp()
        self.script_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        # We need to mock the PROJECT_ROOT logic in hatch.py or set environment
        os.environ["PROJECT_ID"] = "test_project"

        # hatch.py uses script_dir for loader, so we just check outputs
        self.manager = PersonaManager(data_dir=self.test_root)

    def tearDown(self):
        shutil.rmtree(self.test_root)

    def test_cli_accepts_hatch_targets(self):
        parser = build_parser()

        for target in ("pi", "openai", "all"):
            args = parser.parse_args(["--target", target])
            self.assertEqual(args.target, target)

        legacy_args = parser.parse_args(["--client", "pi"])
        self.assertEqual(legacy_args.target, "pi")

    def test_all_hatches_shared_engine_and_real_adapters(self):
        legacy_agent = os.path.join(
            self.test_root,
            "agents",
            "arnalbam-opencode.md",
        )
        os.makedirs(os.path.dirname(legacy_agent), exist_ok=True)
        with open(legacy_agent, "w", encoding="utf-8") as agent_file:
            agent_file.write("legacy generated artifact")

        hatch_prompt(
            "all",
            persona_override="arnalbam",
            output_root=self.test_root,
        )

        skill_path = os.path.join(
            self.test_root,
            "skills",
            "jacazul-engine",
            "SKILL.md",
        )
        self.assertTrue(os.path.isfile(skill_path))

        copilot_agent = os.path.join(
            self.test_root,
            "agents",
            "arnalbam-copilot.md",
        )
        self.assertTrue(os.path.isfile(copilot_agent))

        opencode_agent = os.path.join(
            self.test_root,
            "agents",
            "jacazul-opencode.md",
        )
        self.assertTrue(os.path.isfile(opencode_agent))
        with open(opencode_agent, encoding="utf-8") as agent_file:
            self.assertIn("{💪} Arnalbam", agent_file.read())
        self.assertFalse(
            os.path.exists(
                os.path.join(self.test_root, "agents", "arnalbam-opencode.md")
            )
        )

        for target in ("pi", "openai"):
            agent_path = os.path.join(
                self.test_root,
                "agents",
                f"arnalbam-{target}.md",
            )
            self.assertFalse(os.path.exists(agent_path))

    def test_hatch_output_does_not_depend_on_the_project(self):
        # One hatched copy is linked into every project, so a project ID
        # baked into it points agents of other projects at the wrong silo.
        os.environ["PROJECT_ID"] = "other-org_other-project"
        hatch_prompt(
            "all",
            persona_override="arnalbam",
            output_root=self.test_root,
        )

        leaks = []
        for directory, _, files in os.walk(self.test_root):
            for name in files:
                path = os.path.join(directory, name)
                with open(path, encoding="utf-8") as rendered:
                    if "other-org_other-project" in rendered.read():
                        leaks.append(os.path.relpath(path, self.test_root))
        self.assertEqual(leaks, [])

    def test_hatch_renders_broker_safety_contract(self):
        hatch_prompt(
            "pi",
            persona_override="jacazul",
            output_root=self.test_root,
        )

        skill_path = os.path.join(
            self.test_root,
            "skills",
            "jacazul-engine",
            "SKILL.md",
        )
        with open(skill_path, encoding="utf-8") as skill_file:
            rendered_skill = skill_file.read()

        self.assertIn("never raw `gh`", rendered_skill)
        self.assertIn("Explicit ticket format", rendered_skill)
        self.assertIn("do not bypass the vault", rendered_skill)

    def test_bootstrap_uses_runtime_target_once(self):
        fake_bin = os.path.join(
            self.test_root,
            ".jacazul-ai",
            ".venv",
            "bin",
            "jacazul-hatch",
        )
        capture_path = os.path.join(self.test_root, "hatch-args")
        os.makedirs(os.path.dirname(fake_bin), exist_ok=True)
        with open(fake_bin, "w", encoding="utf-8") as fake_hatch:
            fake_hatch.write(
                f"#!/bin/sh\nprintf '%s\\n' \"$@\" > '{capture_path}'\n"
            )
        os.chmod(fake_bin, 0o700)

        env = os.environ.copy()
        env["HOME"] = self.test_root
        env["JACAZUL_HARNESS"] = "pi"
        subprocess.run(
            ["bash", os.path.join(self.script_dir, "scripts/bootstrap/hatch")],
            check=True,
            env=env,
            capture_output=True,
            text=True,
        )

        with open(capture_path, encoding="utf-8") as capture:
            self.assertEqual(capture.read().splitlines(), ["--target", "pi"])

    def test_hatch_gemini_parity(self):
        # This is more of an integration test
        # We check if artifacts are created in the right place
        # The actual hatch.py uses root_dir = script_dir/../..
        # For testing purposes, we'll just run it and check if it crashes
        try:
            hatch_prompt("gemini", persona_override="jacazul")
            hatch_prompt("copilot", persona_override="codana")
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Hatching failed: {e}")

    def test_hatch_includes_active_persona_authority(self):
        hatch_prompt("gemini", persona_override="arnalbam")

        skill_path = os.path.join(
            self.script_dir,
            "skills",
            "jacazul-engine",
            "SKILL.md",
        )
        with open(skill_path, encoding="utf-8") as skill_file:
            rendered_skill = skill_file.read()

        self.assertIn("## Active Persona Authority", rendered_skill)
        self.assertIn("JACAZUL_PERSONA", rendered_skill)
        self.assertIn("never blend their voices", rendered_skill)

    def test_hatch_includes_handoff_visibility_contract(self):
        hatch_prompt("gemini", persona_override="arnalbam")

        engine_dir = os.path.join(self.script_dir, "skills", "jacazul-engine")
        with open(
            os.path.join(engine_dir, "SKILL.md"), encoding="utf-8"
        ) as skill_file:
            rendered_skill = skill_file.read()
        with open(
            os.path.join(engine_dir, "references", "session.md"),
            encoding="utf-8",
        ) as session_file:
            rendered_session = session_file.read()

        # The hub routes to the contract; the reference carries it.
        self.assertIn("`references/session.md`", rendered_skill)
        self.assertIn("## HANDOFF VISIBILITY CONTRACT", rendered_session)
        self.assertIn("focused plan and task", rendered_session)
        self.assertIn("Never say only `context loaded`", rendered_session)
        # The bootstrap delivers the pending note in the opening prompt, so
        # the reference tells the agent what to do when it is there.
        self.assertIn("`📋 Session Handoff` section", rendered_session)

    def test_hatch_routes_e2e_development_to_its_reference(self):
        hatch_prompt("gemini", persona_override="arnalbam")

        engine_dir = os.path.join(self.script_dir, "skills", "jacazul-engine")
        references_dir = os.path.join(engine_dir, "references")
        with open(
            os.path.join(engine_dir, "SKILL.md"), encoding="utf-8"
        ) as skill_file:
            rendered_skill = skill_file.read()
        with open(
            os.path.join(references_dir, "glossary.md"), encoding="utf-8"
        ) as glossary_file:
            rendered_glossary = glossary_file.read()
        with open(
            os.path.join(references_dir, "e2e-development.md"),
            encoding="utf-8",
        ) as e2e_file:
            rendered_e2e = e2e_file.read()

        # Like i&d: the hub alone routes the trigger to the reference; the
        # glossary names the trigger and its non-triggers without a path,
        # since references never point at other references.
        self.assertIn("`references/e2e-development.md`", rendered_skill)
        self.assertIn("not `e2e` alone or end-to-end tests", rendered_skill)
        self.assertIn("## E2E Development", rendered_glossary)
        self.assertIn("**Not a trigger:**", rendered_glossary)
        self.assertNotIn("references/e2e", rendered_glossary)
        self.assertIn("pode implementar E2E", rendered_e2e)
        self.assertIn("## 7. Review the Trail", rendered_e2e)
        # The approval lets the agent commit, close tasks and move the focus
        # while it implements, and that autonomy is only safe when every
        # commit is atomic.
        self.assertIn("**Autonomy:**", rendered_e2e)
        self.assertIn("without asking per commit", rendered_e2e)
        self.assertIn('without asking "Shall I close this?"', rendered_e2e)
        self.assertIn(
            "**Focus:** `done` anchors the next task", rendered_e2e
        )
        self.assertIn("never includes a push", rendered_e2e)
        self.assertIn(
            "Atomicity is what makes that autonomy safe", rendered_e2e
        )
        # The autonomy also lives where the agent always looks: the approval
        # marks the plan, status shows it, and the hub close rules and the
        # router name it, so the always-loaded "ask first" rules never
        # override the approved initiative.
        self.assertIn("`tw-flow e2e <plan>`", rendered_e2e)
        self.assertIn("**E2E exception:**", rendered_skill)
        self.assertIn("the approval is the consent", rendered_skill)
        self.assertIn('("pode implementar E2E")', rendered_skill)
        self.assertIn("`E2E AUTONOMY` in `tw-flow status`", rendered_skill)


if __name__ == "__main__":
    unittest.main()
