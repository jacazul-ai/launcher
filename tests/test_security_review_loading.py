"""Loading guards for security-expert in development and review.

security-expert loads at three moments: the light checklist before a
code change is called done, its topic triggers, and every code review
as a code-review extension. These guards pin the surfaces that make the
first and last moments happen, and the code-review core changes that
keep one severity scale and stay agnostic about which language skill
the operator uses.
"""

import pathlib
import re
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
CODE_REVIEW = PROJECT_ROOT / "skills" / "code-review" / "SKILL.md"
TEMPLATES = (
    "jacazul/hatch/templates/core/responsibilities.md",
    "jacazul/hatch/templates/agent_master.md",
)


def _read(relative):
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def _section(text, heading):
    match = re.search(
        rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match, f"missing section {heading!r}"
    return match.group(1)


class TestCodeReviewCore(unittest.TestCase):
    def setUp(self):
        self.text = CODE_REVIEW.read_text(encoding="utf-8")

    def test_security_expert_is_a_review_extension(self):
        extensions = _section(self.text, "Language-specific extensions")
        self.assertIn("../security-expert/CODE-REVIEW.md", extensions)
        self.assertRegex(extensions, r"\| Any diff \| `security-expert`")

    def test_security_mapping_covers_scanners_only(self):
        self.assertNotIn("reports formal audits with Critical", self.text)
        mapping = _section(self.text, "Security scanner mapping")
        high = next(
            line for line in mapping.splitlines() if line.startswith("| High")
        )
        self.assertIn("`WARNING`", high)

    def test_entry_points_follow_the_language_skill_in_use(self):
        self.assertIn("language skill in use", self.text)
        self.assertIn("core-only", self.text)

    def test_self_review_tip_walks_the_light_checklist(self):
        tips = _section(self.text, "Bizus (tips that fire by situation)")
        self.assertIn("light checklist", tips)
        self.assertIn("security-expert", tips)


class TestEngineTemplates(unittest.TestCase):
    def test_templates_load_security_expert_for_light_and_review(self):
        for template in TEMPLATES:
            text = " ".join(_read(template).split())
            self.assertIn("light checklist", text, template)
            self.assertRegex(
                text, r"every (code )?review[^.]*security-expert", template
            )


class TestProjectPin(unittest.TestCase):
    def test_agents_pins_the_review_depth(self):
        section = _section(_read("AGENTS.md"), "Security Review")
        self.assertIn("- depth: medium", section)


if __name__ == "__main__":
    unittest.main()
