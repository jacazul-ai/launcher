"""Structure guards for the security-expert hub and its references.

The skill is a thin hub plus one-level references, the go-expert layout.
The risks these guards pin are the ones a reorganization introduces
silently: a reference nobody routes to, a routed file that does not
exist, a nested chain that truncates, a second severity scale competing
with code-review, and tool usage creeping back into a name-only catalog.
"""

import pathlib
import re
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = PROJECT_ROOT / "skills" / "security-expert"
REFERENCES = SKILL_DIR / "references"
EXPECTED_REFERENCES = {
    "threat-modeling.md",
    "ci-cd.md",
    "secrets.md",
    "supply-chain.md",
    "sast.md",
    "auth-and-web.md",
    "cloud-and-containers.md",
    "agent-tools.md",
    "tools.md",
}
ROOT_FILES = {"SKILL.md", "CODE-REVIEW.md"}
HUB_MAX_LINES = 150
# Jacazul language experts; the language pointer must stay skill-agnostic.
LANGUAGE_SKILLS = (
    "go-expert",
    "python-expert",
    "rust-expert",
    "js-ts-expert",
    "zig-expert",
    "php-expert",
    "bash-expert",
)
LINK = re.compile(r"\]\(([^)#\s]+)")


def _read(path):
    return path.read_text(encoding="utf-8")


def _skill_files():
    return sorted(SKILL_DIR.rglob("*.md"))


def _frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md has no frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(": ")
        fields[key] = value.strip().strip('"')
    return fields


class TestSecurityExpertStructure(unittest.TestCase):
    def setUp(self):
        self.hub = _read(SKILL_DIR / "SKILL.md")

    def test_frontmatter_names_the_directory(self):
        fields = _frontmatter(self.hub)
        self.assertEqual(fields["name"], "security-expert")
        self.assertLess(len(fields["description"]), 1000)

    def test_hub_stays_thin(self):
        self.assertLessEqual(len(self.hub.splitlines()), HUB_MAX_LINES)

    def test_references_are_the_expected_set(self):
        found = {path.name for path in REFERENCES.glob("*.md")}
        self.assertEqual(found, EXPECTED_REFERENCES)

    def test_no_loose_catalog_at_the_root(self):
        found = {path.name for path in SKILL_DIR.glob("*.md")}
        self.assertEqual(found, ROOT_FILES)

    def test_every_reference_is_routed_from_the_hub(self):
        routed = set(LINK.findall(self.hub))
        for name in EXPECTED_REFERENCES:
            self.assertIn(f"references/{name}", routed, name)

    def test_every_hub_link_resolves(self):
        for target in LINK.findall(self.hub):
            if "://" in target:
                continue
            self.assertTrue((SKILL_DIR / target).is_file(), target)

    def test_references_are_one_level_deep(self):
        for path in REFERENCES.glob("*.md"):
            for target in LINK.findall(_read(path)):
                self.assertFalse(
                    target.endswith(".md") and "://" not in target,
                    f"{path.name} chains to {target}",
                )

    def test_snyk_has_no_operational_role(self):
        for path in _skill_files():
            self.assertNotIn("snyk", _read(path).lower(), path.name)

    def test_tools_catalog_lists_names_without_usage(self):
        text = _read(REFERENCES / "tools.md")
        self.assertNotIn("```", text)

    def test_no_competing_severity_scale(self):
        for path in _skill_files():
            text = _read(path)
            self.assertNotIn("Priority:", text, path.name)
            self.assertNotIn("Critical/High", text, path.name)
            self.assertNotIn("needs_validation", text, path.name)

    def test_language_pointer_names_no_skill(self):
        for path in (SKILL_DIR / "SKILL.md", SKILL_DIR / "CODE-REVIEW.md"):
            text = _read(path)
            for skill in LANGUAGE_SKILLS:
                self.assertNotIn(skill, text, f"{path.name} names {skill}")
            self.assertIn("language skill in use", text, path.name)

    def test_hub_carries_the_light_checklist(self):
        self.assertIn("## Light Checklist", self.hub)
        self.assertIn("warn once", self.hub.lower())

    def test_hub_records_the_sandbox_gap(self):
        self.assertRegex(self.hub, r"TODO[^\n]*sandbox")

    def test_review_extension_uses_the_core_scale(self):
        text = _read(SKILL_DIR / "CODE-REVIEW.md")
        for label in ("BLOCKER", "HEURISTIC", "SECURITY"):
            self.assertIn(label, text)
        for depth in ("`low`", "`medium`", "`high`"):
            self.assertIn(depth, text)
        self.assertIn("## Security Review", text)


if __name__ == "__main__":
    unittest.main()
