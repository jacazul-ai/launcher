#!/usr/bin/env python
import os
import json
import unittest
from unittest.mock import patch, MagicMock
from .base import JacazulTest
from jacazul.cli.broker import GitHubBroker

# 🐊 Jacazul GitHub Broker Unit Tests
# Verifies hierarchical vault, caching, and invalidation logic.


class TestGitHubBroker(JacazulTest):
    def setUp(self):
        super().setUp()
        # Create an isolated vault directory within the test directory
        self.vault_dir = os.path.join(self.test_dir, "vault")
        os.makedirs(self.vault_dir, exist_ok=True)

        # We need to mock TaskWrapper so it doesn't call real 'task' during
        # init
        with patch("jacazul.cli.broker.TaskWrapper"):
            self.broker = GitHubBroker(vault_dir=self.vault_dir)

    def test_hierarchical_token_resolution(self):
        """Test that tokens are resolved with correct precedence."""
        vault_data = {
            "github": {
                "classic": {"default": "classic_token_enc"},
                "owners": {
                    "my-org": {
                        "token": "org_token_enc",
                        "projects": {"my-proj": "proj_token_enc"},
                    }
                },
            }
        }
        with open(self.broker.vault_file, "w") as f:
            json.dump(vault_data, f)

        # 1. Mock decrypt (Surgical mock on the instance)
        with patch.object(
            self.broker,
            "_decrypt",
            side_effect=lambda x: x.replace("_enc", ""),
        ):
            # 1.1. Test Project precedence
            token = self.broker._get_token(org="my-org", project="my-proj")
            self.assertEqual(token, "proj_token")

            # 1.2. Test Org precedence
            token = self.broker._get_token(org="my-org", project="other-proj")
            self.assertEqual(token, "org_token")

            # 1.3. Test Classic fallback
            token = self.broker._get_token(org="other-org")
            self.assertEqual(token, "classic_token")

    def test_cache_logic_and_ttl(self):
        """Test that metadata is cached and respects TTL."""
        repo = "test/repo"
        kind = "labels"
        data = [{"name": "bug"}]

        # 1. Write to cache
        self.broker._write_cache(repo, kind, data)
        cache_file = self.broker._get_cache_file(repo, kind)
        self.assertTrue(os.path.exists(cache_file))

        # 2. Read from cache (within TTL)
        cached_data = self.broker._read_cache(repo, kind, 3600)
        self.assertEqual(cached_data, data)

        # 3. Read from cache (expired TTL)
        cached_data = self.broker._read_cache(
            repo, kind, -1
        )  # Already expired
        self.assertIsNone(cached_data)

    def test_cache_invalidation_on_write(self):
        """Test that cache is cleared after a write operation."""
        repo = "test/repo"
        self.broker._write_cache(repo, "labels", [{"name": "bug"}])
        self.broker._write_cache(repo, "milestones", [{"title": "v1"}])

        repo_path = os.path.join(self.broker.cache_dir, repo.replace("/", "_"))
        self.assertTrue(os.path.exists(repo_path))

        # 1. Mock context and gh execution (avoiding real world)
        with patch.object(
            self.broker, "_infer_context", return_value=("test", "repo")
        ):
            with patch.object(
                self.broker, "_run_gh", return_value=MagicMock(returncode=0)
            ):
                # Perform a 'close' operation (which should invalidate cache)
                # Redirect stdout for silence during tests
                with patch("sys.stdout"):
                    self.broker.close_issue("1", repo=repo)

        # Check that cache dir was removed
        self.assertFalse(os.path.exists(repo_path))

    def test_sync_issue_closes_task(self):
        """
        Test that sync_issue identifies CLOSED status and completes the task.
        """
        issue_id = "#123"
        repo = "org/proj"

        # 1. Mock gh output (Issue is CLOSED)
        mock_gh_res = MagicMock(returncode=0)
        mock_gh_res.stdout = json.dumps(
            {"state": "CLOSED", "title": "Fix bug"}
        )

        # 2. Mock TaskWrapper export result
        self.broker.tw.export.return_value = [
            {"uuid": "deadbeef-1234", "description": "Local Task"}
        ]

        with patch.object(self.broker, "_run_gh", return_value=mock_gh_res):
            with patch("sys.stdout"):
                self.broker.sync_issue(issue_id, repo=repo)

        # 3. Verify TaskWrapper interaction
        # It should export tasks with externalid:#123
        self.broker.tw.export.assert_called()
        call_args = self.broker.tw.export.call_args[0][0]
        self.assertIn("externalid:#123", call_args)

        # It should run modify commands to set OUTCOME and status:completed
        # We expect at least two calls to run() for the found task
        self.assertGreaterEqual(self.broker.tw.run.call_count, 2)

        # Check if status:completed was sent
        run_calls = [c[0][0] for c in self.broker.tw.run.call_args_list]
        self.assertTrue(any("status:completed" in args for args in run_calls))

    def test_sync_issue_annotates_outcome_without_touching_title(self):
        """
        'modify annotation:...' is not an attribute, so Taskwarrior took it
        as the new description and the task lost its title.
        """
        mock_gh_res = MagicMock(returncode=0)
        mock_gh_res.stdout = json.dumps(
            {"state": "CLOSED", "title": "Fix bug"}
        )
        self.broker.tw.export.return_value = [
            {"uuid": "deadbeef-1234", "description": "Local Task"}
        ]

        with (
            patch.object(self.broker, "_run_gh", return_value=mock_gh_res),
            patch("sys.stdout"),
        ):
            self.broker.sync_issue("#123", repo="org/proj")

        run_calls = [c[0][0] for c in self.broker.tw.run.call_args_list]
        self.assertIn(
            [
                "deadbeef-1234",
                "annotate",
                (
                    "OUTCOME: Automatically closed by Broker sync. "
                    "GitHub issue #123 is CLOSED."
                ),
            ],
            run_calls,
        )
        for args in run_calls:
            self.assertFalse(
                any(arg.startswith("annotation:") for arg in args),
                f"modify rewrites the description: {args}",
            )


if __name__ == "__main__":
    unittest.main()
