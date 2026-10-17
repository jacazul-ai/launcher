#!/usr/bin/env python
import os
import subprocess
import sys
import json
import re
import time
from typing import Optional, Any, Tuple
from jacazul.taskwarrior.core import TaskWrapper

# 🐊 Jacazul GitHub Broker (The Protocol)
# Handles synchronization between Taskwarrior and GitHub via IdZoid security.

DEFAULT_DECRYPT_TIMEOUT = 30

# A token is a keyword argument only when it looks like `key=value` with a
# lowercase identifier key. Anything else stays positional, so ordinary values
# carrying '=' keep working. A keyword-shaped token with an unknown key is an
# error rather than a positional: guessing is what let arguments land in the
# wrong slot in the first place.
KWARG_PATTERN = re.compile(r"^([a-z][a-z0-9_]*)=(.*)$", re.DOTALL)

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _split_list(raw: Optional[str]) -> list:
    """Expands a comma-separated option into a list of trimmed values."""
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_timeout(name: str, default: int) -> int:
    """Reads a positive integer timeout from the environment."""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class GitHubBroker:
    def __init__(
        self,
        vault_dir: Optional[str] = None,
        vault_name: Optional[str] = None,
        cryptozoid_bin: Optional[str] = None,
    ):
        self.tw = TaskWrapper()
        self.vault_dir = vault_dir or os.environ.get(
            "JACAZUL_HOME", os.path.expanduser("~/.jacazul-ai")
        )
        self.vault_name = vault_name or "jacazul-vault"
        self.vault_file = os.path.join(self.vault_dir, "vault.json")
        self.github_vault_legacy = os.path.join(self.vault_dir, "github.enc")
        self.cache_dir = os.path.join(self.vault_dir, "cache", "github")
        self.cryptozoid_bin = cryptozoid_bin or os.path.expanduser(
            "~/go/bin/cryptozoid"
        )
        self.decrypt_timeout = _env_timeout(
            "JACAZUL_BROKER_DECRYPT_TIMEOUT", DEFAULT_DECRYPT_TIMEOUT
        )

    def _ensure_cache_dir(self, repo: str):
        path = os.path.join(self.cache_dir, repo.replace("/", "_"))
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return path

    def _get_cache_file(self, repo: str, kind: str) -> str:
        repo_path = self._ensure_cache_dir(repo)
        return os.path.join(repo_path, f"{kind}.json")

    def _read_cache(
        self, repo: str, kind: str, ttl_seconds: int
    ) -> Optional[Any]:
        """Reads data from local cache if not expired."""
        cache_file = self._get_cache_file(repo, kind)
        if not os.path.exists(cache_file):
            return None

        # Check TTL
        mtime = os.path.getmtime(cache_file)
        if (time.time() - mtime) > ttl_seconds:
            return None

        try:
            with open(cache_file, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_cache(self, repo: str, kind: str, data: Any):
        """Writes data to local cache."""
        cache_file = self._get_cache_file(repo, kind)
        try:
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Warning: Failed to write cache: {e}", file=sys.stderr)

    def _invalidate_cache(self, repo: str, kind: Optional[str] = None):
        """Invalidates cache for a specific repo and kind (or all kinds)."""
        repo_path = self._ensure_cache_dir(repo)
        if kind:
            cache_file = os.path.join(repo_path, f"{kind}.json")
            if os.path.exists(cache_file):
                os.remove(cache_file)
        else:
            import shutil

            shutil.rmtree(repo_path, ignore_errors=True)

    def _decrypt(self, encrypted_blob: str) -> Optional[str]:
        """Decrypts a blob using cryptozoid ec decrypt."""
        if not os.path.exists(self.cryptozoid_bin):
            return None

        cmd = [
            self.cryptozoid_bin,
            "ec",
            "decrypt",
            "-n",
            self.vault_name,
            "-p",
            self.vault_dir,
            encrypted_blob,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.decrypt_timeout,
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            # 🐊 Error as Prompt: a silent hang teaches nothing. A stuck
            # decrypt used to block the calling agent forever with no output.
            print(
                f"⏱️ Token decryption timed out after "
                f"{self.decrypt_timeout}s.\n"
                "   ACTION: Another process may hold the vault. Retry; if it "
                "persists, check for stuck 'cryptozoid ec decrypt' processes "
                "or raise JACAZUL_BROKER_DECRYPT_TIMEOUT.",
                file=sys.stderr,
            )
            return None
        except Exception:
            return None

    def _infer_context(self) -> Tuple[Optional[str], Optional[str]]:
        """Infers Org and Project from the current git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "-v"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Match SSH or HTTPS patterns
            # git@github.com:org/repo.git or https://github.com/org/repo.git
            pattern = r"github\.com[:/](?P<org>[^/]+)/(?P<repo>[^.\s]+)"
            match = re.search(pattern, result.stdout)
            if match:
                return match.group("org"), match.group("repo")
        except Exception:
            pass
        return None, None

    def _get_token(
        self, org: Optional[str] = None, project: Optional[str] = None
    ) -> Optional[str]:
        """Resolves the best GitHub token from vault.json or legacy vault."""

        # 1. Try vault.json (Hierarchical)
        if os.path.exists(self.vault_file):
            try:
                with open(self.vault_file, "r") as f:
                    vault = json.load(f).get("github", {})

                # Precedence: Project > Org > User > Classic Default
                owners = vault.get("owners", {})

                # Check Project level
                if org and project:
                    proj_token = (
                        owners.get(org, {}).get("projects", {}).get(project)
                    )
                    if proj_token:
                        return self._decrypt(proj_token)

                # Check Org/Owner level
                if org:
                    org_token = owners.get(org, {}).get("token")
                    if org_token:
                        return self._decrypt(org_token)

                # Check Classic Default
                classic_default = vault.get("classic", {}).get("default")
                if classic_default:
                    return self._decrypt(classic_default)

            except Exception as e:
                print(
                    f"⚠️ Warning: Failed to read vault.json: {e}",
                    file=sys.stderr,
                )

        # 2. Try legacy github.enc
        if os.path.exists(self.github_vault_legacy):
            try:
                with open(self.github_vault_legacy, "r") as f:
                    blob = f.read().strip()
                return self._decrypt(blob)
            except Exception:
                pass

        return None

    def _run_gh(
        self,
        args: list,
        repo: Optional[str] = None,
        use_repo_flag: bool = True,
    ) -> subprocess.CompletedProcess:
        """Runs a gh command with the best resolved token injected."""

        # Infer context if repo is provided
        target_org = None
        target_proj = None

        if repo:
            if "/" in repo:
                target_org, target_proj = repo.split("/", 1)
        else:
            # Try to infer from current git environment
            target_org, target_proj = self._infer_context()
            if target_org and target_proj:
                if use_repo_flag:
                    repo = f"{target_org}/{target_proj}"

        token = self._get_token(org=target_org, project=target_proj)

        env = os.environ.copy()
        if token:
            env["GH_TOKEN"] = token

        cmd = ["gh"] + args
        if repo and use_repo_flag:
            cmd += ["--repo", repo]

        return subprocess.run(cmd, capture_output=True, text=True, env=env)

    def sync_issue(self, issue_id: str, repo: Optional[str] = None):
        """
        Syncs a GitHub issue status with Taskwarrior and closes task if needed.
        """
        # Strip # if present
        clean_id = issue_id.lstrip("#")

        # Resolve repo for display
        display_repo = repo
        if not display_repo:
            org, proj = self._infer_context()
            if org and proj:
                display_repo = f"{org}/{proj}"

        print(
            f"🐊 Syncing issue #{clean_id} from "
            f"{display_repo or 'current repo'}..."
        )

        result = self._run_gh(
            ["issue", "view", clean_id, "--json", "state,title"], repo=repo
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            state = data.get("state", "UNKNOWN").upper()
            title = data.get("title", "")
            print(f"✅ GitHub Status: {state} | {title}")

            if state == "CLOSED":
                # Find local tasks with this externalid
                tasks = self.tw.export(
                    [f"externalid:#{clean_id}", "status:pending"]
                )
                if not tasks:
                    # Try without # just in case
                    tasks = self.tw.export(
                        [f"externalid:{clean_id}", "status:pending"]
                    )

                if tasks:
                    print(
                        f"🐊 Found {len(tasks)} pending task(s) for this "
                        "ticket. Closing..."
                    )

                    for task in tasks:
                        uuid = task["uuid"]
                        outcome = (
                            f"Automatically closed by Broker sync. "
                            f"GitHub issue #{clean_id} is CLOSED."
                        )
                        # Record outcome first (MANDATORY in tw-flow done)
                        self.tw.run([uuid, "annotate", f"OUTCOME: {outcome}"])
                        self.tw.run([uuid, "modify", "status:completed"])
                        print(f"✅ Task {uuid[:8]} closed locally.")
                else:
                    print("ℹ️ No pending local tasks found for this ticket.")
        else:
            print(f"❌ Error fetching issue: {result.stderr}", file=sys.stderr)

    def open_issue(
        self,
        title: str,
        body: Optional[str] = None,
        body_file: Optional[str] = None,
        repo: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[list] = None,
    ):
        """Opens a new GitHub issue."""
        args = ["issue", "create", "--title", title]
        if body_file:
            args += ["--body-file", body_file]
        elif body:
            args += ["--body", body]
        # 'gh issue create' takes --assignee; 'gh issue edit' does not.
        for login in _split_list(assignee):
            args += ["--assignee", login]
        if labels:
            for label in labels:
                args += ["--label", label]

        result = self._run_gh(args, repo=repo)
        if result.returncode == 0:
            # Invalidate cache on success
            if not repo:
                org, proj = self._infer_context()
                repo = f"{org}/{proj}" if org and proj else None
            if repo:
                self._invalidate_cache(repo)

            # gh issue create prints the URL of the new issue
            issue_url = result.stdout.strip()
            print(f"✅ Issue created: {issue_url}")
            return issue_url
        else:
            print(
                f"❌ Failed to create issue: {result.stderr}", file=sys.stderr
            )
            return None

    def list_labels(self, repo: Optional[str] = None):
        """Lists available labels in the repository (with cache)."""
        if not repo:
            org, proj = self._infer_context()
            if org and proj:
                repo = f"{org}/{proj}"

        if not repo:
            print(
                "❌ Error: Could not infer repository context.",
                file=sys.stderr,
            )
            return

        # Try cache (24h TTL)
        cached = self._read_cache(repo, "labels", 86400)
        if cached:
            print(f"🐊 Labels for {repo} (Cached):")
            for label in cached:
                print(f"  - {label['name']}: {label.get('description', '')}")
            return

        result = self._run_gh(
            ["label", "list", "--json", "name,description"], repo=repo
        )
        if result.returncode == 0:
            labels = json.loads(result.stdout)
            self._write_cache(repo, "labels", labels)
            print(f"🐊 Labels for {repo} (API):")
            for label in labels:
                print(f"  - {label['name']}: {label.get('description', '')}")
        else:
            print(
                f"❌ Failed to list labels: {result.stderr}", file=sys.stderr
            )

    def list_milestones(self, repo: Optional[str] = None):
        """Lists available milestones in the repository (with cache)."""
        # Infer context if not provided
        if not repo:
            org, proj = self._infer_context()
            if org and proj:
                repo = f"{org}/{proj}"

        if not repo:
            print(
                "❌ Error: Could not infer repository context.",
                file=sys.stderr,
            )
            return

        # Try cache (1h TTL)
        cached = self._read_cache(repo, "milestones", 3600)
        if cached:
            print(f"🐊 Milestones for {repo} (Cached):")
            for ms in cached:
                print(f"  - [{ms['number']}] {ms['title']} ({ms['state']})")
            return

        # Use api with the full path. gh api doesn't support --repo flag
        endpoint = f"repos/{repo}/milestones"
        result = self._run_gh(
            ["api", endpoint], repo=None, use_repo_flag=False
        )
        if result.returncode == 0:
            milestones = json.loads(result.stdout)
            self._write_cache(repo, "milestones", milestones)
            if not milestones:
                print(f"ℹ️ No milestones found in {repo}.")
                return
            print(f"🐊 Milestones for {repo} (API):")
            for ms in milestones:
                print(f"  - [{ms['number']}] {ms['title']} ({ms['state']})")
        else:
            print(
                f"❌ Failed to list milestones: {result.stderr}",
                file=sys.stderr,
            )

    def edit_issue(
        self,
        issue_id: str,
        title: Optional[str] = None,
        body: Optional[str] = None,
        body_file: Optional[str] = None,
        repo: Optional[str] = None,
        assignee: Optional[str] = None,
        add_labels: Optional[list] = None,
        remove_labels: Optional[list] = None,
        remove_assignee: Optional[str] = None,
    ):
        """Edits an existing GitHub issue."""
        clean_id = issue_id.lstrip("#")
        args = ["issue", "edit", clean_id]
        if title:
            args += ["--title", title]
        if body_file:
            args += ["--body-file", body_file]
        elif body:
            args += ["--body", body]
        # 'gh issue edit' only knows --add-assignee / --remove-assignee.
        # '@me' and '@copilot' pass through to gh untouched.
        for login in _split_list(assignee):
            args += ["--add-assignee", login]
        for login in _split_list(remove_assignee):
            args += ["--remove-assignee", login]
        if add_labels:
            for label in add_labels:
                args += ["--add-label", label]
        if remove_labels:
            for label in remove_labels:
                args += ["--remove-label", label]

        result = self._run_gh(args, repo=repo)
        if result.returncode == 0:
            # Invalidate cache on success
            if not repo:
                org, proj = self._infer_context()
                repo = f"{org}/{proj}" if org and proj else None
            if repo:
                self._invalidate_cache(repo)

            print(f"✅ Issue #{clean_id} updated.")
        else:
            print(
                f"❌ Failed to update issue: {result.stderr}", file=sys.stderr
            )

    def comment_issue(
        self,
        issue_id: str,
        body: Optional[str] = None,
        body_file: Optional[str] = None,
        repo: Optional[str] = None,
    ):
        """Adds a comment to an existing GitHub issue."""
        clean_id = issue_id.lstrip("#")
        args = ["issue", "comment", clean_id]
        if body_file:
            args += ["--body-file", body_file]
        elif body:
            args += ["--body", body]

        result = self._run_gh(args, repo=repo)
        if result.returncode == 0:
            print(f"✅ Comment added to issue #{clean_id}.")
        else:
            print(
                f"❌ Failed to comment on issue: {result.stderr}",
                file=sys.stderr,
            )

    def close_issue(
        self,
        issue_id: str,
        repo: Optional[str] = None,
        comment: Optional[str] = None,
    ):
        """Closes a GitHub issue with an optional comment."""
        clean_id = issue_id.lstrip("#")
        args = ["issue", "close", clean_id]
        if comment:
            args += ["--comment", comment]

        result = self._run_gh(args, repo=repo)
        if result.returncode == 0:
            # Invalidate cache on success
            if not repo:
                org, proj = self._infer_context()
                repo = f"{org}/{proj}" if org and proj else None
            if repo:
                self._invalidate_cache(repo)

            print(f"✅ Issue #{clean_id} closed.")
        else:
            print(
                f"❌ Failed to close issue: {result.stderr}", file=sys.stderr
            )

    def view_issue(self, issue_id: str, repo: Optional[str] = None):
        """Fetches and displays full details of a GitHub issue."""
        clean_id = issue_id.lstrip("#")
        result = self._run_gh(
            [
                "issue",
                "view",
                clean_id,
                "--json",
                "number,title,state,body,labels,assignees,createdAt",
            ],
            repo=repo,
        )
        if result.returncode != 0:
            print(
                f"❌ Failed to fetch issue: {result.stderr}", file=sys.stderr
            )
            return

        data = json.loads(result.stdout)
        state = data.get("state", "UNKNOWN").upper()
        title = data.get("title", "")
        body = data.get("body", "")
        labels = [lb["name"] for lb in data.get("labels", [])]
        assignees = [a["login"] for a in data.get("assignees", [])]

        print(f"🐊 Issue #{clean_id} [{state}] — {title}")
        if labels:
            print(f"   Labels: {', '.join(labels)}")
        if assignees:
            print(f"   Assignees: {', '.join(assignees)}")
        print()
        print(body)

    def list_issues(
        self,
        repo: Optional[str] = None,
        state: str = "open",
        milestone: Optional[str] = None,
        limit: int = 30,
    ):
        """Lists issues in the repository."""
        args = ["issue", "list", "--state", state, "--limit", str(limit)]
        if milestone:
            args += ["--milestone", milestone]

        args += ["--json", "number,title,state,updatedAt"]

        result = self._run_gh(args, repo=repo)
        if result.returncode == 0:
            issues = json.loads(result.stdout)
            if not issues:
                print(
                    f"ℹ️ No {state} issues found in {repo or 'current repo'}."
                )
                return

            print(
                f"🐊 {state.capitalize()} issues for {repo or 'current repo'}:"
            )
            for issue in issues:
                print(
                    f"  - [#{issue['number']}] {issue['title']} "
                    f"({issue['state']})"
                )
        else:
            print(
                f"❌ Failed to list issues: {result.stderr}", file=sys.stderr
            )


def error(msg: str):
    """🐊 Error as Prompt: Emits error to stderr with ACTION hints."""
    print(f"❌ ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg: str):
    """Emits a non-fatal deprecation or advisory notice to stderr."""
    print(f"⚠️ {msg}", file=sys.stderr)


USAGE = """Usage: jacazul-broker <command> [args...] [key="value"...]

Commands:
  view <id> [repo=]             Shows full issue details and body
  sync <id> [repo=]             Syncs issue status to local tasks
  list [repo=] [state=]         Lists issues (state: open|closed|all)
       [milestone=]
  labels [repo=]                Lists repository labels (cached)
  milestones [repo=]            Lists repository milestones (cached)
  open title= [body=]           Creates a new issue
       [body_file=] [repo=]
       [assignee=] [labels=]
  edit <id> [title=] [body=]    Updates an existing issue
       [body_file=] [repo=]
       [assignee=]
       [remove_assignee=]
       [add_labels=]
       [remove_labels=]
  comment <id> body= | body_file=
                                Adds a comment to an issue
       [repo=]
  close <id> [repo=]            Closes an issue
        [comment=]

Repository:
  Every command accepts repo="org/name". When omitted, the repository is
  inferred from the current git remote.
  view, sync, list, labels, milestones and close still accept the repository
  as a positional argument, but that form is deprecated and warns.

Lists:
  labels=, add_labels=, remove_labels=, assignee= and remove_assignee= accept
  comma-separated values, e.g. labels="bug,enhancement". Use "@me" or
  "@copilot" for assignee logins.

Positional placeholder:
  Use "-" to skip a positional argument, e.g. 'jacazul-broker list - closed'.

Shell quoting:
  Quote issue ids that carry '#', otherwise the shell treats the rest of the
  line as a comment: jacazul-broker view '#106'

Examples:
  jacazul-broker view '#106'
  jacazul-broker list repo="jacazul-ai/jacazul-ai-sandbox" state="closed"
  jacazul-broker open title="Broken flag" labels="bug" \\
    repo="jacazul-ai/jacazul-ai-sandbox"
  jacazul-broker edit '#106' assignee="@me"
  jacazul-broker comment '#106' body_file="/tmp/comment.md"

💡 Tip: For complex Markdown bodies (backticks, quotes, newlines), prefer
   body_file="/path/to/body.md" over body="..."."""


def print_usage():
    print(USAGE)


def split_args(
    cmd: str, args: list, slots: list, allowed: set, hint: str = ""
) -> Tuple:
    """Splits argv into positional slots and validated keyword arguments.

    Fails closed: unknown keyword keys and positional tokens beyond the
    declared slots abort with an ACTION hint instead of being dropped.
    """
    kwargs = {}
    positionals = []

    for arg in args:
        match = KWARG_PATTERN.match(arg)
        if match:
            key, value = match.group(1), match.group(2)
            if key not in allowed:
                accepted = ", ".join(f"{k}=" for k in sorted(allowed))
                error(
                    f"Unknown argument '{key}=' for '{cmd}'.\n"
                    f"   ACTION: Accepted keywords: {accepted or 'none'}."
                )
            kwargs[key] = value
        else:
            positionals.append(arg)

    values = {}
    for index, name in enumerate(slots):
        raw = positionals[index] if index < len(positionals) else None
        values[name] = None if raw == "-" else raw

    declared = len(slots)
    extra = positionals[declared:]
    if extra:
        guidance = hint or (
            f"'{cmd}' takes {declared} positional argument(s). "
            'Pass the repository as repo="org/name".'
        )
        error(
            f"Unexpected argument '{extra[0]}' for '{cmd}'.\n"
            f"   ACTION: {guidance}"
        )

    return values, kwargs


def pick(cmd: str, name: str, positional: Optional[str], kwargs: dict):
    """Resolves a value that accepts both a deprecated positional and a
    keyword form. Supplying both is an error."""
    keyword = kwargs.get(name)
    if positional is None:
        return keyword
    if keyword is not None:
        error(
            f"'{name}' given twice for '{cmd}'.\n"
            f'   ACTION: Use only {name}="{keyword}".'
        )
    warn(
        f"Positional '{name}' is deprecated for '{cmd}'.\n"
        f'   ACTION: Use {name}="{positional}" instead.'
    )
    return positional


def validate_repo(repo: Optional[str]) -> Optional[str]:
    """Rejects malformed repository values before gh is invoked."""
    if repo is None:
        return None
    if not REPO_PATTERN.match(repo):
        error(
            f"Invalid repository '{repo}'.\n"
            '   ACTION: Use repo="org/name", e.g. '
            'repo="jacazul-ai/jacazul-ai-sandbox".'
        )
    return repo


def require_id(cmd: str, issue_id: Optional[str], example: str = "") -> str:
    """Enforces the issue id positional shared by most commands.

    The example keeps the id quoted, because an unquoted '#' turns the rest
    of the shell line into a comment.
    """
    if not issue_id:
        usage = example or f'jacazul-broker {cmd} "#123"'
        error(f"Issue ID required for '{cmd}'.\n   ACTION: Use '{usage}'")
    return issue_id


def main():
    broker = GitHubBroker()

    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h", "help"):
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in ("view", "sync"):
        slots, allowed = ["issue_id", "repo"], {"repo"}
        pos, kwargs = split_args(cmd, args, slots, allowed)
        issue_id = require_id(cmd, pos["issue_id"])
        repo = validate_repo(pick(cmd, "repo", pos["repo"], kwargs))
        if cmd == "view":
            broker.view_issue(issue_id, repo)
        else:
            broker.sync_issue(issue_id, repo)

    elif cmd == "list":
        slots = ["repo", "state", "milestone"]
        allowed = {"repo", "state", "milestone"}
        pos, kwargs = split_args(cmd, args, slots, allowed)
        repo = validate_repo(pick(cmd, "repo", pos["repo"], kwargs))
        state = pick(cmd, "state", pos["state"], kwargs) or "open"
        milestone = pick(cmd, "milestone", pos["milestone"], kwargs)
        broker.list_issues(repo, state, milestone)

    elif cmd in ("labels", "milestones"):
        pos, kwargs = split_args(cmd, args, ["repo"], {"repo"})
        repo = validate_repo(pick(cmd, "repo", pos["repo"], kwargs))
        if cmd == "labels":
            broker.list_labels(repo)
        else:
            broker.list_milestones(repo)

    elif cmd == "open":
        allowed = {
            "title",
            "body",
            "body_file",
            "repo",
            "assignee",
            "labels",
        }
        _, kwargs = split_args(
            cmd,
            args,
            [],
            allowed,
            hint=(
                "Use 'jacazul-broker open title=\"My title\"'. "
                "'open' takes no positional arguments."
            ),
        )
        title = kwargs.get("title")
        if not title:
            error(
                "Title required to open issue.\n"
                "   ACTION: Use 'jacazul-broker open title=\"My title\"'"
            )
        broker.open_issue(
            title,
            kwargs.get("body"),
            kwargs.get("body_file"),
            validate_repo(kwargs.get("repo")),
            kwargs.get("assignee"),
            _split_list(kwargs.get("labels")) or None,
        )

    elif cmd == "edit":
        allowed = {
            "title",
            "body",
            "body_file",
            "repo",
            "assignee",
            "remove_assignee",
            "add_labels",
            "remove_labels",
        }
        pos, kwargs = split_args(cmd, args, ["issue_id"], allowed)
        issue_id = require_id(cmd, pos["issue_id"])
        broker.edit_issue(
            issue_id,
            kwargs.get("title"),
            kwargs.get("body"),
            kwargs.get("body_file"),
            validate_repo(kwargs.get("repo")),
            kwargs.get("assignee"),
            _split_list(kwargs.get("add_labels")) or None,
            _split_list(kwargs.get("remove_labels")) or None,
            kwargs.get("remove_assignee"),
        )

    elif cmd == "comment":
        allowed = {"body", "body_file", "repo"}
        pos, kwargs = split_args(cmd, args, ["issue_id"], allowed)
        example = 'jacazul-broker comment "#123" body="My comment"'
        issue_id = require_id(cmd, pos["issue_id"], example)
        body = kwargs.get("body")
        body_file = kwargs.get("body_file")
        if not body and not body_file:
            error(f"Comment body required.\n   ACTION: Use '{example}'")
        broker.comment_issue(
            issue_id, body, body_file, validate_repo(kwargs.get("repo"))
        )

    elif cmd == "close":
        slots = ["issue_id", "repo", "comment"]
        allowed = {"repo", "comment"}
        pos, kwargs = split_args(cmd, args, slots, allowed)
        issue_id = require_id(cmd, pos["issue_id"])
        repo = validate_repo(pick(cmd, "repo", pos["repo"], kwargs))
        comment = pick(cmd, "comment", pos["comment"], kwargs)
        broker.close_issue(issue_id, repo, comment)

    else:
        print(USAGE, file=sys.stderr)
        error(
            f"Unknown command: '{cmd}'.\n"
            "   ACTION: Use one of: view, sync, list, labels, milestones, "
            "open, edit, comment, close."
        )


if __name__ == "__main__":
    main()
