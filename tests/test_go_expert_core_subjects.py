"""Content guards for the six core subjects compared against upstream.

Each of these subjects already had a local reference when the upstream
comparison began, so the risk is not an empty file — it is a reference
that looks complete while missing the conventions a Go reviewer would
actually cite. These guards pin what the depth comparison added.
"""

import pathlib
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
REFERENCES = PROJECT_ROOT / "skills" / "go-expert" / "references"


def _read(name):
    return (REFERENCES / name).read_text(encoding="utf-8")


class TestGoExpertCoreSubjects(unittest.TestCase):
    def _covers(self, name, markers):
        content = _read(name).lower()
        for marker in markers:
            self.assertTrue(
                marker.lower() in content,
                f"{name} no longer covers {marker!r}",
            )

    def test_naming_covers_the_conventions_a_reviewer_cites(self):
        self._covers(
            "naming.md",
            (
                "MixedCaps",
                "stutter",
                "receiver",
                "acronym",
                "Err",
                "Must",
            ),
        )

    def test_naming_keeps_the_anti_java_material(self):
        """The depth comparison must enrich, never displace."""
        self._covers("naming.md", ("IThing", "BaseThing", "premature"))

    def test_errors_covers_the_wrapping_decisions(self):
        self._covers(
            "errors.md",
            ("errors.Join", "errcheck", "%v", "errors.AsType"),
        )

    def test_context_covers_origin_values_and_detachment(self):
        self._covers(
            "context.md",
            (
                "context.Background",
                "context.TODO",
                "WithoutCancel",
                "unexported",
                "context.Cause",
            ),
        )

    def test_concurrency_covers_the_primitive_details(self):
        self._covers(
            "concurrency.md",
            (
                "RWMutex",
                "atomic.Int64",
                "errgroup",
                "wg.Go",
                "OnceValue",
                "sync.Map",
            ),
        )

    def test_testing_covers_isolation_and_the_stdlib_helpers(self):
        self._covers(
            "testing.md",
            (
                "t.Parallel",
                "t.Setenv",
                "testing/synctest",
                "go:build",
                "Example",
                "Fuzz",
            ),
        )

    def test_documentation_covers_the_markers_tooling_reads(self):
        self._covers(
            "documentation.md",
            ("Deprecated:", "doc link", "go:generate", "why"),
        )

    def test_security_covers_the_go_specific_surface(self):
        self._covers(
            "security.md",
            (
                "os.Root",
                "ConstantTimeCompare",
                "html/template",
                "InsecureSkipVerify",
                "security-expert",
            ),
        )

    def test_profiling_teaches_reading_a_profile(self):
        """The command surface alone is not the skill; reading it is."""
        self._covers(
            "profiling.md",
            (
                "flat",
                "runtime.mallocgc",
                "runtime.scanobject",
                "peek",
                "-base",
                "goroutineleak",
                "debug=2",
                "pprof.Do",
            ),
        )

    def test_profiling_teaches_reading_a_trace(self):
        self._covers(
            "profiling.md",
            (
                "runnable",
                "mark assist",
                "-pprof=sched",
                "trace.NewTask",
                "WithRegion",
                "FlightRecorder",
                "MaxBytes",
            ),
        )

    def test_security_covers_the_language_references_in_depth(self):
        """Second pass over the five upstream security references."""
        self._covers(
            "security.md",
            (
                "ORDER BY",
                "Dialer",
                "hmac.Equal",
                "crypto/pbkdf2",
                "ReadHeaderTimeout",
                "MaxBytesReader",
                "CreateTemp",
                "encoding/gob",
                "archive",
            ),
        )

    def test_performance_covers_layout_and_allocation_depth(self):
        """Second pass over upstream cpu.md and memory.md."""
        self._covers(
            "performance.md",
            (
                "*[]byte",
                "false sharing",
                "CacheLinePad",
                "strings.Clone",
                "-m -m",
                "asynchronous preemption",
                "slices.Equal",
            ),
        )

    def test_packages_covers_the_module_mechanics(self):
        self._covers(
            "packages.md",
            ("internal/", "go.work", "go.sum", "gopls"),
        )

    def test_packages_covers_semantic_import_versioning(self):
        self._covers(
            "packages.md",
            (
                "Semantic Import Versioning",
                "import compatibility rule",
                "+incompatible",
                "go.dev/ref/mod#major-version-suffixes",
            ),
        )


if __name__ == "__main__":
    unittest.main()
