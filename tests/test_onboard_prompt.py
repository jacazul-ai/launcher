import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "prompts" / "onboard.md"
RENDERER = PROJECT_ROOT / "scripts" / "bootstrap" / "onboard"
LAUNCHERS = (
    "scripts/jacazul-claude",
    "scripts/jacazul-pi",
    "scripts/jacazul-gemini",
)
# Each removed rule must stay reachable: the prompt names where it lives.
POINTERS = (
    '"Terminal-First Anti-Token-Waste"',
    '"Core Principles"',
    '"Environment Modes"',
    '"Context Orientation"',
    '"Reference Router"',
    "references/onboard.md",
    "references/session.md",
    "references/collaboration.md",
)
# Signatures and voice slang belong to a persona's own specification.
PERSONA_VOICE = re.compile(
    r"🐊 Jacazul|\{🔷\}|\{💪\}|\{🦉\}|tá ligado|\bquiridu\b|\bbarão\b"
)


class OnboardPromptTest(unittest.TestCase):
    """One template feeds every launcher prompt, as an index of the engine."""

    def test_template_is_an_index_of_the_engine(self):
        text = TEMPLATE.read_text(encoding="utf-8")

        for pointer in POINTERS:
            self.assertIn(pointer, text, pointer)
        self.assertNotIn("## 🧬 CORE PRINCIPLES", text)
        self.assertNotIn("REPRODUCE the last full output", text)
        # The renderer expands the template through a shell heredoc.
        self.assertNotIn("`", text)
        self.assertNotIn("$(", text)

    def test_rendered_prompt_is_small_and_ends_with_the_voice(self):
        rendered = self._render("arnalbam")
        voice = (
            PROJECT_ROOT
            / "jacazul"
            / "hatch"
            / "templates"
            / "persona"
            / "persona_arnalbam.md"
        ).read_text(encoding="utf-8")

        index = rendered.split(voice.strip().splitlines()[0])[0]
        self.assertLess(len(index.encode("utf-8")), 2_600)
        self.assertTrue(rendered.rstrip().endswith(voice.rstrip()))
        self.assertIn("{💪} Arnalbam", index)
        self.assertNotIn("$JACAZUL", rendered)

    def test_launchers_render_the_shared_template(self):
        for launcher in LAUNCHERS:
            source = (PROJECT_ROOT / launcher).read_text(encoding="utf-8")
            self.assertIn("scripts/bootstrap/onboard", source, launcher)
            self.assertNotIn("multi_agent_loop.md", source, launcher)
            self.assertNotIn("CORE PRINCIPLES", source, launcher)

    def test_prompt_text_carries_no_persona_voice(self):
        # Only text that reaches the model: terminal banners and comments
        # may carry the brand. The runtime tests check the captured prompt.
        sandboxed = (
            PROJECT_ROOT / "scripts" / "jacazul-gemini-sandboxed"
        ).read_text(encoding="utf-8")
        renderer = RENDERER.read_text(encoding="utf-8")
        prompt_text = {
            "prompts/onboard.md": TEMPLATE.read_text(encoding="utf-8"),
            "scripts/bootstrap/onboard": "\n".join(
                line
                for line in renderer.splitlines()
                if not line.lstrip().startswith("#")
            ),
            "scripts/jacazul-gemini-sandboxed": next(
                line
                for line in sandboxed.splitlines()
                if line.startswith('ONBOARD_PROMPT="')
            ),
        }
        for name, text in prompt_text.items():
            self.assertEqual(PERSONA_VOICE.findall(text), [], name)

    def test_pending_handoff_reaches_the_opening_prompt(self):
        # Backticks and $ in a note must arrive verbatim, never expanded.
        note = "## Next action\nRun `make test` and check $HOME.\n"

        rendered = self._render("arnalbam", note=note)

        self.assertIn("📋 Session Handoff", rendered)
        self.assertIn(note.strip(), rendered)
        self.assertIn("tw-flow focus", rendered)
        self.assertIn("tw-flow session ack", rendered)
        self.assertIn("next action", rendered)

    def test_acknowledged_handoff_is_not_injected(self):
        note = "## Next action\nShip it.\n\nacknowledged: 2026-10-18\n"

        rendered = self._render("arnalbam", note=note)

        self.assertEqual(rendered, self._render("arnalbam"))
        self.assertNotIn("Session Handoff", rendered)

    def test_handoff_of_another_session_is_not_injected(self):
        rendered = self._render(
            "arnalbam", note="## Next action\nShip it.\n", note_id="other"
        )

        self.assertNotIn("Session Handoff", rendered)
        self.assertNotIn("Ship it.", rendered)

    @staticmethod
    def _render(
        persona: str, note: str | None = None, note_id: str = "abc12345"
    ) -> str:
        with tempfile.TemporaryDirectory(prefix="onboard-prompt-") as home:
            project_id = "onboard-prompt-test"
            # Anchor the persona the way jacazul-persona does.
            anchor = Path(home) / ".task" / project_id / "persona.json"
            anchor.parent.mkdir(parents=True)
            anchor.write_text(
                json.dumps({"anchored_persona": persona}), encoding="utf-8"
            )
            if note is not None:
                (anchor.parent / f"session-note-{note_id}.md").write_text(
                    note, encoding="utf-8"
                )
            env = os.environ.copy()
            env.pop("TASKDATA", None)
            env.update(
                {
                    "PROJECT_ROOT": str(PROJECT_ROOT),
                    "JACAZUL_HOME": home,
                    "PROJECT_ID": project_id,
                    "JACAZUL_HARNESS": "claude",
                    "JACAZUL_SESSION_ID": "abc12345",
                }
            )
            return subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; source "$2"; printf "%s" "$ONBOARD_PROMPT"',
                    "bash",
                    str(PROJECT_ROOT / "scripts" / "bootstrap" / "persona"),
                    str(RENDERER),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            ).stdout


if __name__ == "__main__":
    unittest.main()
