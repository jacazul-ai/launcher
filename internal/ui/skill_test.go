package ui

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// The ui-expert skill ships to every harness, so its verification scheme
// must be one every harness can run. A tool that only one harness provides
// crossing into the skill text breaks that, and this test fails first.
func TestUIExpertNamesNoSingleHarnessTool(t *testing.T) {
	root := filepath.Join("..", "..", "skills", "ui-expert")
	files := []string{filepath.Join(root, "SKILL.md"), filepath.Join(root, "CODE-REVIEW.md")}
	refs, err := filepath.Glob(filepath.Join(root, "references", "*.md"))
	if err != nil || len(refs) == 0 {
		t.Fatalf("no references under %s: %v", root, err)
	}
	files = append(files, refs...)

	tools := []string{
		"claude-in-chrome",
		"claude in chrome",
		"computer_use",
		"computer use",
		"mcp__",
		"claude.ai",
		"anthropic",
	}
	for _, path := range files {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		content := strings.ToLower(string(data))
		for _, tool := range tools {
			if strings.Contains(content, tool) {
				t.Errorf("%s names %q: verification must use open tooling every harness runs (AGENTS.md, Generic by Default)", path, tool)
			}
		}
	}
}
