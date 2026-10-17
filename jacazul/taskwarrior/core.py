import hashlib
import os
import shutil
import subprocess
import orjson
import re
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

# 🐊 tw_expert Core Module (v1.5.0)
# Centralized logic for Environment, Taskwarrior, Cache, and Focus management.


class CacheManager:
    STATUS_TTL = 120  # 2 minutes
    PONDER_TTL = 600  # 10 minutes
    PLANS_TTL = 300  # 5 minutes

    def __init__(self, taskdata: str):
        jacazul_home = os.environ.get(
            "JACAZUL_HOME", os.path.expanduser("~/.jacazul-ai")
        )
        project_id = os.environ.get("PROJECT_ID", os.path.basename(taskdata))
        session_id = os.environ.get("JACAZUL_SESSION_ID", "global")
        self.cache_dir = os.path.join(
            jacazul_home, "cache", "tw-flow", project_id, session_id
        )

    def _ensure_dir(self):
        os.makedirs(self.cache_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def _hash(self, output: str) -> str:
        return hashlib.sha256(output.encode()).hexdigest()[:16]

    def get(self, key: str, ttl: int) -> Optional[str]:
        path = self._path(key)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            data = orjson.loads(f.read())
        if time.time() - data["ts"] > ttl:
            return None
        return data["output"]

    def set(self, key: str, output: str):
        self._ensure_dir()
        with open(self._path(key), "wb") as f:
            f.write(
                orjson.dumps(
                    {
                        "hash": self._hash(output),
                        "output": output,
                        "ts": time.time(),
                    }
                )
            )

    def bust(self, ini_name: Optional[str] = None, focus_change: bool = False):
        """Invalidate every derived workflow view after state changes."""
        del ini_name, focus_change
        if not os.path.exists(self.cache_dir):
            return

        cache_prefixes = ("status", "ponder", "plans")
        for filename in os.listdir(self.cache_dir):
            if filename.startswith(cache_prefixes) and filename.endswith(
                ".json"
            ):
                os.remove(os.path.join(self.cache_dir, filename))

    def clear(self, scope: Optional[str] = None):
        if not os.path.exists(self.cache_dir):
            return
        if scope is None:
            shutil.rmtree(self.cache_dir)
        else:
            for f in os.listdir(self.cache_dir):
                if f.startswith(scope):
                    os.remove(os.path.join(self.cache_dir, f))

    def info(self) -> Dict[str, Any]:
        if not os.path.exists(self.cache_dir):
            return {"files": 0, "dir": self.cache_dir}
        files = os.listdir(self.cache_dir)
        return {"files": len(files), "dir": self.cache_dir, "entries": files}


class Environment:
    @staticmethod
    def get_mode() -> str:
        return os.environ.get("JACAZUL_MODE", "SANDBOXED")

    @staticmethod
    def get_project_id() -> str:
        return os.environ.get("PROJECT_ID", "global")

    @staticmethod
    def get_jacazul_home() -> str:
        return os.path.expanduser("~/.jacazul-ai")

    @staticmethod
    def get_taskrc() -> str:
        if "TASKRC" in os.environ:
            return os.environ["TASKRC"]
        jacazul_rc = os.path.join(Environment.get_jacazul_home(), ".taskrc")
        if os.path.exists(jacazul_rc):
            return jacazul_rc
        return os.path.expanduser("~/.taskrc")

    @staticmethod
    def get_taskdata() -> str:
        # If TASKDATA is explicitly set in env, we MUST respect it (e.g. tests)
        if "TASKDATA" in os.environ:
            return os.environ["TASKDATA"]

        project_id = Environment.get_project_id().split(":")[0]
        home = Environment.get_jacazul_home()
        return os.path.join(home, ".task", project_id)

    @staticmethod
    def get_real_task_bin() -> str:
        if "JACAZUL_REAL_TASK" in os.environ:
            return os.environ["JACAZUL_REAL_TASK"]

        try:
            # We want to avoid our own scripts/task wrapper
            res = subprocess.run(
                ["which", "-a", "task"],
                capture_output=True,
                text=True,
                check=False,
            )
            bins = res.stdout.strip().split("\n")
            for b in bins:
                if "scripts/task" not in b:
                    return b
        except Exception:
            pass
        return "/usr/bin/task"


class TaskWrapper:
    def __init__(self):
        self.bin = Environment.get_real_task_bin()
        self.rc = Environment.get_taskrc()
        self.data = Environment.get_taskdata()
        os.makedirs(self.data, exist_ok=True)

    def run(
        self,
        args: List[str],
        capture: bool = True,
        verbose: Optional[str] = "new-id",
    ) -> subprocess.CompletedProcess:
        cmd = [
            self.bin,
            f"rc:{self.rc}",
            f"rc.data.location={self.data}",
            "rc.confirmation=no",
            "rc.bulk=0",
        ]
        if verbose:
            cmd.append(f"rc.verbose={verbose}")
        cmd.extend(args)

        res = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            env=os.environ.copy(),
            check=False,
        )
        return res

    def export(self, filter_args: List[str] = None) -> List[Dict[str, Any]]:
        args = filter_args or []
        if "export" not in args:
            args.append("export")
        res = self.run(args, capture=True, verbose="no")
        if res.returncode != 0:
            return []
        try:
            return orjson.loads(res.stdout)
        except Exception:
            return []


# 🐊 Jacazul Broker Engine (The Protocol)
# Handles synchronization between Taskwarrior and various Git providers.
#
# INTERFACE DESIGN (Duck Typing):
# Any Broker class MUST implement:
# - sync_issue(issue_id, repo=None)
# - view_issue(issue_id, repo=None)


class GitHubBroker:
    """Implementation for GitHub using 'gh' CLI."""

    def __init__(self):
        self.tw = TaskWrapper()
        self.vault_dir = os.environ.get(
            "JACAZUL_HOME", os.path.expanduser("~/.jacazul-ai")
        )
        self.cryptozoid_bin = os.path.expanduser("~/go/bin/cryptozoid")

    def sync_issue(self, issue_id: str, repo: Optional[str] = None):
        # Implementation delegated to the broker binary for security
        # This is a bridge to the CLI experience
        subprocess.run(
            ["jacazul-broker", "sync", issue_id] + ([repo] if repo else [])
        )

    def view_issue(self, issue_id: str, repo: Optional[str] = None):
        subprocess.run(
            ["jacazul-broker", "view", issue_id] + ([repo] if repo else [])
        )


class BitbucketBroker:
    """Implementation for Bitbucket/Jira (Mocked/Stubbed)."""

    def sync_issue(self, issue_id: str, repo: Optional[str] = None):
        print(f"🐊 [Bitbucket/Jira] Mock Syncing ticket {issue_id}...")
        print(f"✅ Status: MOCKED (Pattern: {issue_id})")

    def view_issue(self, issue_id: str, repo: Optional[str] = None):
        print(f"🐊 [Bitbucket/Jira] Viewing ticket {issue_id}...")


class BrokerFactory:
    """Decides broker by project context and ticket pattern."""

    @staticmethod
    def _infer_broker_from_git():
        """Infers the broker provider from the current git remote."""
        try:
            # Check for a git remote to anchor project context
            res = subprocess.run(
                ["git", "remote", "-v"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                output = res.stdout.lower()
                if "github.com" in output:
                    return GitHubBroker()
                if "bitbucket.org" in output:
                    return BitbucketBroker()
        except Exception:
            pass
        return None

    @staticmethod
    def get_broker(ticket: str):
        # 1. Check for custom configuration overrides (User is King)
        config_path = os.path.expanduser("~/.jacazul-ai/brokers.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "rb") as f:
                    config = orjson.loads(f.read())

                patterns = config.get("patterns", [])
                for entry in patterns:
                    regex = entry.get("regex")
                    broker_type = entry.get("broker")
                    if regex and broker_type and re.match(regex, ticket):
                        if broker_type.lower() == "github":
                            return GitHubBroker()
                        if broker_type.lower() == "bitbucket":
                            return BitbucketBroker()
            except Exception:
                pass

        # 2. Ticket identity
        # Provider-specific ticket formats are more authoritative than the
        # current repository remote. A project may track work in an external
        # Bitbucket/Jira system while its local mirror lives on GitHub.
        if ticket.startswith("#"):
            return GitHubBroker()
        if re.match(r"^[A-Z0-9]+-[0-9]+$", ticket):
            return BitbucketBroker()

        # 3. Project anchor (Git context)
        # Use the remote only when the ticket itself does not identify a
        # provider.
        git_broker = BrokerFactory._infer_broker_from_git()
        if git_broker:
            return git_broker

        return None


@dataclass
class FocusState:
    focused_plan: Optional[str] = None
    focused_task_uuid: Optional[str] = None
    task_track: List[Dict[str, str]] = None
    plans_of_interest: List[str] = None

    def to_dict(self):
        return asdict(self)


class FocusManager:
    def __init__(self):
        self.data_dir = Environment.get_taskdata()
        self.file_path = os.path.join(self.data_dir, "focus.json")
        session_id = os.environ.get("JACAZUL_SESSION_ID")
        self.session_file_path = (
            os.path.join(self.data_dir, f"focus-{session_id}.json")
            if session_id
            else None
        )

    def _active_file(self) -> str:
        """Return session file if SESSION_ID set, else global focus.json."""
        if self.session_file_path:
            return self.session_file_path
        return self.file_path

    def _read_file(self) -> str:
        """Return session file if SESSION_ID set and exists, else global."""
        if self.session_file_path and os.path.exists(self.session_file_path):
            return self.session_file_path
        return self.file_path

    def load(self) -> FocusState:
        active = self._read_file()

        if not os.path.exists(active):
            return FocusState(task_track=[], plans_of_interest=[])

        try:
            with open(active, "rb") as f:
                data = orjson.loads(f.read())

                # Migration logic: Support both old and new keys
                focused_plan = data.get("focused_plan") or data.get(
                    "focused_ini"
                )
                plans_of_interest = data.get("plans_of_interest") or data.get(
                    "inis_of_interest", []
                )

                # Migrate internal track entries
                track = data.get("task_track", [])
                for entry in track:
                    if "ini" in entry:
                        entry["plan"] = entry.pop("ini")

                return FocusState(
                    focused_plan=focused_plan,
                    focused_task_uuid=data.get("focused_task_uuid"),
                    task_track=track,
                    plans_of_interest=plans_of_interest,
                )
        except Exception:
            return FocusState(task_track=[], plans_of_interest=[])

    def save(self, state: FocusState):
        os.makedirs(self.data_dir, exist_ok=True)
        target = self._active_file()
        with open(target, "wb") as f:
            f.write(orjson.dumps(state.to_dict(), option=orjson.OPT_INDENT_2))

    def update_plan(self, name: str):
        state = self.load()
        state.focused_plan = name
        self.save(state)

    def push_task(self, uuid: str, plan: str):
        state = self.load()
        state.task_track = [
            t for t in state.task_track if t.get("uuid") != uuid
        ]
        state.task_track.insert(0, {"uuid": uuid, "plan": plan})
        state.focused_task_uuid = uuid
        state.focused_plan = plan
        self.save(state)

    def pop_task(self) -> Optional[Dict[str, str]]:
        state = self.load()
        if not state.task_track:
            state.focused_task_uuid = None
            state.focused_plan = None
            self.save(state)
            return None

        state.task_track.pop(0)
        if state.task_track:
            top = state.task_track[0]
            state.focused_task_uuid = top["uuid"]
            state.focused_plan = top.get("plan") or top.get("ini")
        else:
            state.focused_task_uuid = None
            state.focused_plan = None

        self.save(state)
        return state.task_track[0] if state.task_track else None

    def advance(
        self, completed_uuid: str, tw: "TaskWrapper"
    ) -> Optional[Dict[str, str]]:
        """Advance focus within the completed task's plan only.

        No-op if `completed_uuid` isn't the current focus. Otherwise drops
        it from the stack and inspects pending entries from the same plan.
        Entries from another plan are discarded so completion can never
        silently move the anchor into a different plan. When no stacked
        entry of the plan is pending, the plan's most urgent ready task is
        anchored; the focus clears only when the plan has none left.
        """
        state = self.load()
        if state.focused_task_uuid != completed_uuid:
            return None

        completed_entry = next(
            (
                entry
                for entry in state.task_track
                if entry.get("uuid") == completed_uuid
            ),
            None,
        )
        plan = state.focused_plan or (
            completed_entry.get("plan") if completed_entry else None
        )
        same_plan = [
            entry
            for entry in state.task_track
            if entry.get("uuid") != completed_uuid
            and entry.get("plan") == plan
        ]

        for entry in same_plan:
            exported = tw.export([entry["uuid"]])
            status = exported[0].get("status") if exported else None
            if status == "pending":
                state.task_track = same_plan
                state.focused_task_uuid = entry["uuid"]
                state.focused_plan = plan
                self.save(state)
                return entry

        # Nothing stacked is left: anchor the plan's next ready task, so
        # completing the only anchored task never drops the focus mid-plan.
        ready = (
            tw.export([f'project:"{plan}"', "status:pending", "+READY"])
            if plan
            else []
        )
        if ready:
            ready.sort(key=lambda t: (-t.get("urgency", 0), t.get("entry")))
            entry = {"uuid": ready[0]["uuid"], "plan": plan}
            state.task_track = [entry]
            state.focused_task_uuid = entry["uuid"]
            state.focused_plan = plan
            self.save(state)
            return entry

        state.task_track = []
        state.focused_task_uuid = None
        state.focused_plan = None
        self.save(state)
        return None
