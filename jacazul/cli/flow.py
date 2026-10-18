#!/usr/bin/env python
import sys
import os
import re
import io
import orjson
import subprocess
from contextlib import redirect_stdout
from typing import List, Optional, Dict, Any
from importlib.metadata import version as _pkg_version
from jacazul.taskwarrior.core import (
    CacheManager,
    TaskWrapper,
    FocusManager,
    BrokerFactory,
)

try:
    VERSION = _pkg_version("jacazul-ai-cli")
except Exception:
    VERSION = "dev"

# 🐊 tw-flow (v1.6.0)
# Python port of the Taskwarrior Flow manager.

E2E_BANNER = (
    "🔁 E2E AUTONOMY: approved initiative. Commit each task, close it with "
    "an OUTCOME\n"
    "   and let done move the focus, without asking. A push, a history "
    "rewrite,\n"
    "   work outside this plan or a design gap still go to the operator."
)


class FlowManager:
    def __init__(self):
        self.tw = TaskWrapper()
        self.focus = FocusManager()
        self.cache = CacheManager(self.tw.data)

    def error(self, msg: str):
        print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(1)

    def success(self, msg: str):
        print(f"✓ {msg}")

    def cmd_reopen(self, input_id: str):
        uuid = self.resolve_uuid(input_id)
        self.tw.run([uuid, "modify", "status:pending"])
        self.success(f"Task {uuid[:8]} reopened and moved back to PENDING.")

    def cmd_amend(self, input_id: str, updates: List[str]):
        uuid = self.resolve_uuid(input_id)
        args = [uuid, "modify"]
        found = False
        for update in updates:
            if update.startswith("description="):
                args.append(update.replace("description=", "", 1))
                found = True
            elif update.startswith("ticket="):
                args.append(f"externalid:{update.replace('ticket=', '', 1)}")
                found = True

        if not found:
            self.error(
                "No valid fields to amend. "
                'Use description="..." or ticket="..."'
            )

        self.tw.run(args)
        self.success(f"Task {uuid[:8]} metadata amended successfully.")

    def info(self, msg: str):
        print(f"ℹ {msg}")

    @staticmethod
    def _known_value(value: Optional[str]) -> Optional[str]:
        """Return a non-empty runtime value, excluding sentinels."""
        if not value:
            return None
        value = value.strip()
        if value.lower() in {"unspecified", "unknown", "none", "null"}:
            return None
        return value

    @classmethod
    def task_signature(cls) -> str:
        """Build the provenance signature for persistent task annotations."""
        configured = cls._known_value(os.environ.get("JACAZUL_TASK_SIGNATURE"))
        if configured:
            return configured

        persona_names = {
            "jacazul": "Jacazul",
            "codama": "Codama",
            "codana": "Codama",
            "arnalbam": "Arnalbam",
            "atena": "Atena",
        }
        persona = cls._known_value(
            os.environ.get("JACAZUL_PERSONA_NAME")
        ) or persona_names.get(
            os.environ.get("JACAZUL_PERSONA", "jacazul").lower(),
            "Jacazul",
        )
        model = next(
            (
                candidate
                for candidate in (
                    os.environ.get("JACAZUL_MODEL"),
                    os.environ.get("PI_MODEL"),
                    os.environ.get("CLAUDE_MODEL"),
                    os.environ.get("ANTHROPIC_MODEL"),
                    os.environ.get("MODEL"),
                )
                if cls._known_value(candidate)
            ),
            "unspecified",
        )
        harness = (
            cls._known_value(os.environ.get("JACAZUL_HARNESS")) or "unknown"
        )
        session = (
            cls._known_value(os.environ.get("JACAZUL_SESSION_ID")) or "global"
        )
        return (
            f"— {persona} ({model}; harness: {harness}; "
            f"session: {session[:8]})"
        )

    @classmethod
    def signed_annotation(cls, prefix: str, message: str) -> str:
        """Append the runtime provenance to a task annotation."""
        annotation = f"{prefix}: {message}"
        signature = cls.task_signature()
        if not annotation.rstrip().endswith(signature):
            annotation = f"{annotation.rstrip()} {signature}"
        return annotation

    def annotate(self, uuid: str, prefix: str, message: str):
        """Record a signed annotation through the Taskwarrior wrapper."""
        self.tw.run(
            [uuid, "annotate", self.signed_annotation(prefix, message)]
        )

    def warning(self, msg: str):
        print(f"⚠ {msg}")

    def resolve_uuid(self, input_val: str) -> str:
        if re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            input_val,
        ):
            return input_val
        tasks = self.tw.export()
        if input_val.isdigit():
            for t in tasks:
                if str(t.get("id")) == input_val:
                    return t["uuid"]
        if len(input_val) >= 8:
            for t in tasks:
                if t["uuid"].startswith(input_val.lower()):
                    return t["uuid"]
        return input_val

    def invalidate_task_cache(self, input_id: str):
        """Invalidate derived views for a task mutation."""
        uuid = self.resolve_uuid(input_id)
        tasks = self.tw.export([uuid])
        plan = tasks[0].get("project") if tasks else None
        self.cache.bust(ini_name=plan)

    def verify_not_completed(self, uuid: str):
        tasks = self.tw.export([uuid])
        if tasks and tasks[0].get("status") == "completed":
            short = uuid[:8]
            self.error(
                f"Task {short} is already COMPLETED.\n"
                f"   ACTION: To fix metadata (description/ticket), "
                f"use 'tw-flow amend {short} ...'.\n"
                f"   ACTION: To perform more work, "
                f"use 'tw-flow reopen {short}'."
            )

    def find_ticket(
        self, uuid: str, seen: Optional[set] = None
    ) -> Optional[str]:
        if seen is None:
            seen = set()
        if uuid in seen:
            return None
        seen.add(uuid)
        tasks = self.tw.export([uuid])
        if not tasks:
            return None
        task = tasks[0]
        if task.get("externalid"):
            return task["externalid"]
        deps = task.get("depends", [])
        for dep_uuid in deps:
            ticket = self.find_ticket(dep_uuid, seen)
            if ticket:
                return ticket
        return None

    def get_parent_context(self, uuid: str):
        def _collect(u: str, seen: set) -> List[Dict[str, Any]]:
            if u in seen:
                return []
            seen.add(u)
            tasks = self.tw.export([u])
            if not tasks:
                return []
            t = tasks[0]

            results = []
            # Recurse into dependencies first (climb up the tree)
            deps = t.get("depends", [])
            for dep_uuid in deps:
                results.extend(_collect(dep_uuid, seen))

            # Add current task to the list
            # (after its dependencies for top-down order)
            return results + [t]

        # Start collection from parents of the target task
        leaf_tasks = self.tw.export([uuid])
        if not leaf_tasks:
            return

        # We don't want to collect context from the target task itself here
        seen = {uuid}
        all_parents = []
        for dep_uuid in leaf_tasks[0].get("depends", []):
            all_parents.extend(_collect(dep_uuid, seen))

        if all_parents:
            header_shown = False
            for p in all_parents:
                annots = [
                    a["description"]
                    for a in p.get("annotations", [])
                    if re.match(
                        r"^(OUTCOME|DECISION|LESSON|HANDOFF|"
                        r"QUESTION|HYPOTHESIS):",
                        a["description"],
                    )
                ]
                if annots:
                    if not header_shown:
                        print("\n══ INHERITED CONTEXT ══")
                        header_shown = True
                    print(f"Task ({p['uuid'][:8]}) [{p['description']}]:")
                    for a in annots:
                        print(f"  - {a}")
            if header_shown:
                print("")

    def cmd_plan(self, name: str, tasks: List[str]):
        if not name:
            self.error("Plan name required")
        if not tasks:
            self.error("At least one task required")
        self.info(f"Creating plan: {name}")
        prev_uuid = None
        for spec in tasks:
            parts = spec.split("|")
            mode, desc, tag, due = "", "", "implementation", None
            if len(parts) >= 1:
                if parts[0] in [
                    "DESIGN",
                    "SPIKE",
                    "INVESTIGATE",
                    "GUIDE",
                    "EXECUTE",
                    "REFINE",
                    "TEST",
                    "DEBUG",
                    "REVIEW",
                    "PR-REVIEW",
                ]:
                    mode = parts[0]
                    desc = parts[1] if len(parts) > 1 else ""
                    tag = parts[2] if len(parts) > 2 else tag
                    due = parts[3] if len(parts) > 3 else due
                else:
                    desc = parts[0]
                    tag = parts[1] if len(parts) > 1 else tag
                    due = parts[2] if len(parts) > 2 else due
            if not desc:
                self.error("Task description cannot be empty")
            final_desc = f"[{mode}] {desc}" if mode else desc
            priority = "M"
            args = [
                "add",
                f'project:"{name}"',
                final_desc,
                f"priority:{priority}",
                f"+{tag}",
            ]
            if due:
                args.append(f"due:{due}")
            if prev_uuid:
                args.append(f"depends:{prev_uuid}")
            res = self.tw.run(args)
            match = re.search(r"Created task (\d+)", res.stdout)
            if match:
                new_id = match.group(1)
                new_tasks = self.tw.export([new_id])
                if new_tasks:
                    uuid = new_tasks[0]["uuid"]
                    prev_uuid = uuid
                    self.success(
                        f"Created task {uuid[:8]}: {final_desc} "
                        f"[priority: {priority}]"
                    )
            else:
                self.error(
                    f"Failed to create task: {final_desc}\n{res.stderr}"
                )
        self.success(f"Plan created with {len(tasks)} tasks")

    def cmd_rename(self, old_name: str, new_name: str):
        self.info(f"Renaming plan '{old_name}' to '{new_name}'...")

        # 1. Check if plan exists
        tasks = self.tw.export([f'project:"{old_name}"'])
        if not tasks:
            self.error(f"Plan '{old_name}' not found or has no tasks.")

        # 2. Modify tasks in Taskwarrior
        # Use 'yes all' to bypass confirmation if bulk modifying
        res = self.tw.run(
            [
                f'project:"{old_name}"',
                "modify",
                f'project:"{new_name}"',
            ]
        )
        if res.returncode != 0:
            self.error(f"Failed to rename plan in Taskwarrior: {res.stderr}")

        # 3. Synchronize Focus Context
        state = self.focus.load()
        updated = False

        if state.focused_plan == old_name:
            state.focused_plan = new_name
            updated = True

        if old_name in state.plans_of_interest:
            state.plans_of_interest = [
                new_name if i == old_name else i
                for i in state.plans_of_interest
            ]
            state.plans_of_interest = sorted(
                list(set(state.plans_of_interest))
            )
            updated = True

        for entry in state.task_track:
            if entry.get("plan") == old_name:
                entry["plan"] = new_name
                updated = True
            elif entry.get("ini") == old_name:
                entry["plan"] = new_name
                updated = True

        if updated:
            self.focus.save(state)
            self.info("Focus context synchronized with new plan name.")

        self.success(
            f"Plan '{old_name}' successfully renamed to '{new_name}'."
        )

    def cmd_status(
        self,
        filter_val: Optional[str] = None,
        pending_only: bool = False,
        use_table: bool = False,
    ):
        state = self.focus.load()
        plan_name = filter_val or state.focused_plan
        if not plan_name:
            active = self.tw.export(["+ACTIVE"])
            plan_name = active[0].get("project") if active else "ALL ACTIVE"

        filter_args = (
            [f'project:"{plan_name}"'] if plan_name != "ALL ACTIVE" else []
        )
        if pending_only:
            filter_args.append("status:pending")

        tasks = self.tw.export(filter_args)
        # Sort tasks: pending first, then by entry date
        tasks.sort(
            key=lambda x: (0 if x["status"] == "pending" else 1, x["entry"])
        )

        print(f"══ Plan: {plan_name} ══")
        # 🐊 Prompt as Ad: Focus Context
        print("ℹ TIP: 'tw-flow status' is for the current FOCUS (FOCO).")
        print("ℹ Use 'tw-flow focus' for any anchor-related actions.")
        print("ℹ Use 'tw-flow ponder' for the PROJECT-WIDE landscape.\n")

        mode = os.environ.get("JACAZUL_MODE", "COUNSELOR")
        print(f"🛡️  MODE: {mode}")
        focused = (
            self.tw.export([state.focused_task_uuid])
            if state.focused_task_uuid
            else []
        )
        if focused and "e2e" in focused[0].get("tags", []):
            print(E2E_BANNER)
        elif mode != "UNHINGED":
            print(
                "⚠️  RESTRICTION: User confirmation required for Commits/Push."
            )
        print("")

        if plan_name == state.focused_plan:
            print("📌 ANCHORED SESSION")
            session_id = os.environ.get("JACAZUL_SESSION_ID", "global")
            note_path = os.path.join(
                self.focus.data_dir,
                f"session-note-{session_id}.md",
            )
            if os.path.exists(note_path):
                with open(note_path) as f:
                    note_content = f.read()
                if "acknowledged:" not in note_content:
                    print(
                        "📋 SESSION NOTE PENDING — run 'tw-flow session "
                        "resume' to load previous session context before "
                        "proceeding.\n"
                        "   ACTION: Run 'tw-flow session ack' after reading "
                        "to dismiss."
                    )

        if state.focused_task_uuid:
            print(f"\n🎯 FOCUS CONTEXT [{state.focused_task_uuid[:8]}]:")
            self.get_parent_context(state.focused_task_uuid)
            ft_tasks = self.tw.export([state.focused_task_uuid])
            if ft_tasks:
                task = ft_tasks[0]
                ticket = self.find_ticket(task["uuid"])
                if ticket:
                    is_inherited = ticket != task.get("externalid")
                    prefix = "Inherited" if is_inherited else "External"
                    print(
                        f"🐊 ALERT: {prefix} ticket detected "
                        f"({ticket}). Git-expert will use this for "
                        "automated commit referencing."
                    )
                for a in task.get("annotations", []):
                    print(f"  - {a['description']}")

        pending = [t for t in tasks if t["status"] == "pending"]
        completed = [t for t in tasks if t["status"] == "completed"]

        if use_table:
            self.render_status_table(pending, completed, state)
        else:
            self.render_status_list(pending, completed, state)

        print(f"\nTotal: {len(pending)} pending, {len(completed)} completed.")

    def render_status_list(self, pending, completed, state):
        def format_task_line(t):
            uuid_short = t["uuid"][:8]
            mark = (
                " - ACTIVE"
                if t.get("start")
                else (
                    " - FOCUSED"
                    if t["uuid"] == state.focused_task_uuid
                    else ""
                )
            )
            ticket = self.find_ticket(t["uuid"])
            ticket_str = f" [{ticket}]" if ticket else ""
            return f"[{uuid_short}{mark}]{ticket_str} {t['description']}"

        if pending:
            print("\nPENDING:")
            for t in pending:
                print(f"- {format_task_line(t)}")
        if completed:
            print("\nCOMPLETED:")
            for t in completed:
                print(f"  ✓ {format_task_line(t)}")

    def render_status_table(self, pending, completed, state):
        print("\n| ST | UUID | TICKET | DESCRIPTION |")
        print("|---|---|---|---|")

        def format_table_row(t, icon):
            uuid_short = t["uuid"][:8]
            ticket = self.find_ticket(t["uuid"]) or "-"
            desc = t["description"]
            # Highlight focused task in description
            if t["uuid"] == state.focused_task_uuid:
                desc = f"**{desc}**"
            return f"| {icon} | `{uuid_short}` | {ticket} | {desc} |"

        for t in pending:
            icon = "⚡" if t.get("start") else "○"
            if t["uuid"] == state.focused_task_uuid:
                icon = "🎯"
            print(format_table_row(t, icon))

        for t in completed:
            print(format_table_row(t, "✓"))

    def cmd_next(self, filter_val: str = "status:pending"):
        self.info("Next tasks ready to work:")
        print("")
        # We need to capture output to filter out numeric IDs
        args = (
            [filter_val, "ready"]
            if "project:" in filter_val or "status:" in filter_val
            else [f'project:"{filter_val}"', "status:pending", "ready"]
        )
        res = self.tw.run(args, capture=True)
        if res.returncode == 0:
            lines = res.stdout.strip().split("\n")
            for line in lines:
                # Taskwarrior ready report line format:
                # ID Age Tag Urgency Description
                # We want to replace ID with short UUID
                match = re.match(r"^\s*(\d+)\s+", line)
                if match:
                    numeric_id = match.group(1)
                    # Resolve to UUID
                    tasks = self.tw.export([numeric_id])
                    if tasks:
                        uuid_short = tasks[0]["uuid"][:8]
                        new_line = re.sub(r"^\s*\d+", f"  {uuid_short}", line)
                        print(new_line)
                else:
                    # Header or other lines
                    print(line)
        else:
            self.warning("No tasks ready")

    def cmd_execute(self, input_id: str):
        uuid = self.resolve_uuid(input_id)
        self.verify_not_completed(uuid)
        self.get_parent_context(uuid)
        res = self.tw.run([uuid, "start"])
        if res.returncode == 0:
            self.success(f"Started working on task {uuid[:8]}")
            tasks = self.tw.export([uuid])
            project = tasks[0].get("project", "") if tasks else ""
            self.focus.push_task(uuid, project)
            self.tw.run([uuid], capture=False)
        else:
            self.error(f"Failed to start task: {res.stderr}")

    def cmd_done(self, input_id: str, note: Optional[str] = None):
        uuid = self.resolve_uuid(input_id)
        self.verify_not_completed(uuid)
        tasks = self.tw.export([uuid])
        if not tasks:
            self.error("Task not found")

        # 🐊 Python Quality Gate (Vaccinated Tool)
        # Check for modified or untracked .py files in the current context
        res = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            capture_output=True,
            text=True,
            check=False,
        )
        modified_py = [
            line.split()[-1]
            for line in res.stdout.splitlines()
            if line.strip().endswith(".py")
            and os.path.exists(line.split()[-1])
        ]

        if modified_py and os.environ.get("JACAZUL_TESTING") != "true":
            self.info(
                "Python files detected. Running Quality Gate (py-check)..."
            )

            pycheck_bin = os.path.join(
                os.path.expanduser("~/.jacazul-ai"),
                "skills/python-expert/scripts/py-check",
            )
            # Fallback to local path if not in home
            if not os.path.exists(pycheck_bin):
                pycheck_bin = os.path.join(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(os.path.abspath(__file__))
                        )
                    ),
                    "skills/python-expert/scripts/py-check",
                )

            check_res = subprocess.run(
                [pycheck_bin] + modified_py,
                capture_output=False,  # Allow it to print its own beauty
                text=True,
                check=False,
            )
            if check_res.returncode != 0:
                self.error(
                    "Python validation failed. Task completion BLOCKED.\n"
                    "   ACTION: Fix the PEP 8 violations reported above "
                    "before running 'done'."
                )

        if not any(
            "OUTCOME:" in a["description"]
            for a in tasks[0].get("annotations", [])
        ):
            self.error(
                f"Task {uuid[:8]} cannot be completed without an "
                "OUTCOME record.\n   "
                f'Use: tw-flow outcome {uuid[:8]} "your result"'
            )
        if note:
            self.annotate(uuid, "DONE", note)
        os.environ["TW_FLOW_INTERNAL"] = "true"
        res = self.tw.run([uuid, "done"])
        if res.returncode == 0:
            self.success(f"Task {uuid[:8]} completed!")

            next_focus = self.focus.advance(uuid, self.tw)
            if next_focus:
                self.info(
                    f"Focus advanced to: {next_focus['uuid'][:8]} "
                    f"[{next_focus.get('plan')}]"
                )

            # Multi-Broker Protocol Sync
            ticket = self.find_ticket(uuid)
            if ticket:
                broker = BrokerFactory.get_broker(ticket)
                if broker:
                    print("")
                    self.info(
                        f"The Protocol: Synchronizing ticket {ticket}..."
                    )
                    broker.sync_issue(ticket)

            # Check if any tasks were unblocked
            print("")
            self.info("Checking for newly unblocked tasks...")
            # Reuse cmd_next logic for standardized output
            tasks = self.tw.export(["status:pending", "ready", "limit:3"])
            if tasks:
                self.success(f"{len(tasks)} task(s) now ready to work")
                for t in tasks:
                    print(
                        f"  {t['uuid'][:8]} - {t['description']} "
                        f"[{t.get('urgency', 0):.1f}]"
                    )
        else:
            self.error(f"Failed to complete task: {res.stderr}")

    def cmd_outcome(self, input_id: str, msg: str):
        uuid = self.resolve_uuid(input_id)
        self.verify_not_completed(uuid)
        self.annotate(uuid, "OUTCOME", msg)
        self.success(f"Recorded outcome for task {uuid[:8]}")

    def cmd_handoff(self, input_id: str, msg: str):
        uuid = self.resolve_uuid(input_id)
        self.verify_not_completed(uuid)
        self.cmd_execute(uuid)
        self.annotate(uuid, "HANDOFF", msg)
        self.success(f"Handoff to task {uuid[:8]} with note")

    def cmd_notes(self, input_id: str):
        uuid = self.resolve_uuid(input_id)
        tasks = self.tw.export([uuid])
        if not tasks:
            self.error(f"Task {uuid[:8]} not found.")
        annotations = tasks[0].get("annotations", [])
        if not annotations:
            print(f"No annotations on task {uuid[:8]}.")
            return
        print(f"══ Notes for task {uuid[:8]} ══")
        for ann in annotations:
            print(f"  [{ann['entry']}] {ann['description']}")

    def cmd_note(self, input_id: str, note_type: str, msg: str):
        uuid = self.resolve_uuid(input_id)
        if note_type.lower() in ("delete", "del"):
            tasks = self.tw.export([uuid])
            if not tasks:
                self.error(f"Task {uuid[:8]} not found.")
            annotations = tasks[0].get("annotations", [])
            match = next((a for a in annotations if a["entry"] == msg), None)
            if not match:
                self.error(
                    f"No annotation found with timestamp [{msg}] on task "
                    f"{uuid[:8]}.\n"
                    f"   ACTION: Run 'tw-flow notes {uuid[:8]}' to list "
                    f"valid timestamps."
                )
            self.tw.run([uuid, "denotate", match["description"]])
            self.success(f"Deleted annotation [{msg}] from task {uuid[:8]}")
            return
        prefixes = {
            "research": "RESEARCH",
            "r": "RESEARCH",
            "decision": "DECISION",
            "d": "DECISION",
            "outcome": "OUTCOME",
            "o": "OUTCOME",
            "handoff": "HANDOFF",
            "h": "HANDOFF",
            "blocked": "BLOCKED",
            "b": "BLOCKED",
            "lesson": "LESSON",
            "l": "LESSON",
            "question": "QUESTION",
            "q": "QUESTION",
            "hypothesis": "HYPOTHESIS",
            "y": "HYPOTHESIS",
            "ac": "AC",
            "a": "AC",
            "note": "NOTE",
            "n": "NOTE",
            "link": "LINK",
        }
        prefix = prefixes.get(note_type.lower())
        if not prefix:
            allowed = ", ".join(sorted(set(p for p in prefixes.values())))
            self.error(
                f"Invalid note type: '{note_type}'.\n   "
                f"ACTION: Use one of the allowed semantic types: {allowed}"
            )
        self.annotate(uuid, prefix, msg)
        self.success(f"Added {prefix} note to task {uuid[:8]}")

    def cmd_ticket(self, input_id: str, ticket: str):
        uuid = self.resolve_uuid(input_id)
        self.verify_not_completed(uuid)

        # Linking never syncs: a sync of a CLOSED issue closes every pending
        # task already linked to it, so linking several tasks to a closed
        # issue would close the ones linked first.
        self.tw.run([uuid, "modify", f"externalid:{ticket}"])
        self.success(f"Task {uuid[:8]} linked to ticket: {ticket}")

    def cmd_e2e(self, plan_name: str):
        tasks = self.tw.export([f'project:"{plan_name}"', "status:pending"])
        if not tasks:
            self.error(
                f"Plan '{plan_name}' has no pending tasks to mark as E2E.\n"
                "   ACTION: Run 'tw-flow plans' and pass the approved "
                "initiative's name."
            )
        res = self.tw.run(
            [f'project:"{plan_name}"', "status:pending", "modify", "+e2e"]
        )
        if res.returncode != 0:
            self.error(f"Failed to mark plan {plan_name}: {res.stderr}")
        self.success(
            f"Plan {plan_name} marked as E2E ({len(tasks)} pending task(s))."
        )
        print(E2E_BANNER)

    def commit_footer_type(self, ticket: str, is_fix: bool = False) -> str:
        """Select Fixes only when no pending task remains for a ticket."""
        if is_fix:
            return "Fixes"

        pending_tasks = self.tw.export(["status:pending"])
        has_pending = any(
            task.get("status") == "pending"
            and task.get("externalid") == ticket
            for task in pending_tasks
        )
        return "Refs" if has_pending else "Fixes"

    def cmd_commit(self, is_fix: bool = False):
        state = self.focus.load()
        uuid = state.focused_task_uuid
        if not uuid:
            active = self.tw.export(["+ACTIVE"])
            if active:
                uuid = active[0]["uuid"]

        if not uuid:
            self.error("No active or focused task found to generate commit.")
            return

        tasks = self.tw.export([uuid])
        if not tasks:
            self.error("Task not found.")
            return

        task = tasks[0]
        desc = task["description"]
        ticket = self.find_ticket(uuid)

        # Determine prefix from interaction mode
        prefix = "feat"
        if "[DESIGN]" in desc or "[SPIKE]" in desc:
            prefix = "docs"
        elif "[DEBUG]" in desc or "[BUG]" in desc:
            prefix = "fix"
        elif "[TEST]" in desc:
            prefix = "test"
        elif "[REFINE]" in desc or "[REFACTOR]" in desc:
            prefix = "refactor"

        # Clean description (remove mode and initiative name if present)
        clean_desc = re.sub(r"\[[A-Z-]+\]\s*", "", desc).lower()

        mode = os.environ.get("JACAZUL_MODE", "COUNSELOR")
        print("\n══ DRAFT CONVENTIONAL COMMIT ══")
        print(f"{prefix}: {clean_desc}")

        if mode != "UNHINGED":
            if ticket:
                ref_type = self.commit_footer_type(ticket, is_fix)
                print(f"\n{ref_type}: {ticket}")
            print("═══════════════════════════════")
            print("\n🛡️  SAFETY GATE: Manual Confirmation Required.")
            print("   AGENT ACTION: Present this draft to the user and WAIT.")
            print(
                "   The 'git commit' command must not be executed "
                "automatically."
            )
            print(
                "   MESSAGE: Use 'git commit -F <file>' for bodies; "
                "reserve -m for title-only commits."
            )
            return

        print("\n[Body: explain what and why...]")

        if ticket:
            ref_type = self.commit_footer_type(ticket, is_fix)
            print(f"\n{ref_type}: {ticket}")
        print("═══════════════════════════════")
        self.info(
            "Write the body to a message file and use "
            "'git commit -F <file>'; do not pass body text through -m."
        )

    def cmd_context(self, input_id: str):
        uuid = self.resolve_uuid(input_id)
        self.info(f"Full context for task {uuid[:8]}:")
        print("")
        verbose = (
            "affected,header,foot,label,columns,subtotal,"
            "stats,history,project,context,annotations"
        )
        self.tw.run([uuid, "info"], capture=False, verbose=verbose)

    def cmd_backlog(self, plan_name: str):
        """Move a plan to backlog state (hidden from default views)."""
        tasks = self.tw.export([f'project:"{plan_name}"', "status:pending"])
        if not tasks:
            self.error(f"No pending tasks found for plan: {plan_name}")
            return
        for t in tasks:
            self.tw.run([t["uuid"], "modify", "backlog:1"])
        self.cache.bust(ini_name=plan_name)
        self.success(f"Plan '{plan_name}' moved to backlog. 💤")

    def cmd_activate(self, plan_name: str):
        """Move a backlog plan back to active state."""
        tasks = self.tw.export([f'project:"{plan_name}"', "status:pending"])
        if not tasks:
            self.error(f"No pending tasks found for plan: {plan_name}")
            return
        for t in tasks:
            self.tw.run([t["uuid"], "modify", "backlog:0"])
        self.cache.bust(ini_name=plan_name)
        self.success(f"Plan '{plan_name}' activated. ●")

    def cmd_roadmap(self):
        """Render the strategic roadmap ledger grouped by phase."""
        project_id = os.environ.get("PROJECT_ID", "")
        roadmap_plan = f"{project_id}-roadmap"
        phases_order = [
            "in-progress",
            "next",
            "blocked",
            "future",
            "shipped",
            "cancelled",
        ]
        phase_icons = {
            "in-progress": "▶",
            "next": "→",
            "blocked": "⛔",
            "future": "◌",
            "shipped": "✓",
            "cancelled": "✗",
        }

        tasks = self.tw.export([f'project:"{roadmap_plan}"', "status:pending"])
        tasks += self.tw.export(
            [f'project:"{roadmap_plan}"', "status:completed"]
        )
        if not tasks:
            self.info(
                "No roadmap found. Run 'tw-flow roadmap init' to create one."
            )
            return

        by_phase: Dict[str, List[Dict[str, Any]]] = {}
        for t in tasks:
            p = t.get("phase") or "future"
            by_phase.setdefault(p, []).append(t)

        print(f"\n══ ROADMAP: {project_id} ══\n")
        for phase in phases_order:
            if phase not in by_phase:
                continue
            icon = phase_icons.get(phase, "○")
            print(f"[{phase.upper()}]")
            for t in by_phase[phase]:
                desc = t.get("description", "?")
                ini = t.get("operational_ini", "")
                uuid_short = t["uuid"][:8]
                ini_status = ""
                if ini:
                    pending = self.tw.export(
                        [f'project:"{ini}"', "status:pending"]
                    )
                    completed = self.tw.export(
                        [f'project:"{ini}"', "status:completed"]
                    )
                    if not pending and completed:
                        ini_status = "✓ shipped"
                    elif pending:
                        active_tasks = [p for p in pending if p.get("start")]
                        ini_status = (
                            f"● pending:{len(pending)}"
                            f" active:{len(active_tasks)}"
                        )
                    else:
                        ini_status = "? no tasks"
                    if ini != desc:
                        ini_str = f" → {ini} [{ini_status}]"
                    else:
                        ini_str = f" [{ini_status}]"
                else:
                    ini_str = ""
                print(f"  {icon} `{uuid_short}` {desc}{ini_str}")
            print("")

    def cmd_roadmap_init(self):
        """Discover existing inis and build roadmap ledger projection."""
        project_id = os.environ.get("PROJECT_ID", "")
        roadmap_plan = f"{project_id}-roadmap"

        # Check if roadmap already exists (pending or completed)
        existing = self.tw.export(
            [f'project:"{roadmap_plan}"', "status:pending"]
        )
        existing += self.tw.export(
            [f'project:"{roadmap_plan}"', "status:completed"]
        )
        if existing:
            self.error(
                f"Roadmap already initialized: {roadmap_plan}. "
                "Use 'tw-flow roadmap' to view it."
            )
            return

        # Discover all inis
        all_tasks = self.tw.export(["status:pending"])
        all_tasks += self.tw.export(["status:completed"])
        plans: Dict[str, Dict[str, Any]] = {}
        for t in all_tasks:
            p = t.get("project", "")
            if (
                not p
                or p.endswith("-roadmap")
                or "_archive" in p
                or "_trash" in p
            ):
                continue
            if p not in plans:
                plans[p] = {"pending": 0, "completed": 0, "active": 0}
            if t["status"] == "pending":
                plans[p]["pending"] += 1
                if t.get("start"):
                    plans[p]["active"] += 1
            elif t["status"] == "completed":
                plans[p]["completed"] += 1

        # Classify
        # in-progress = has at least one task with start set (actively running)
        # next = has pending tasks but none started
        # future = zero pending and zero completed (never touched)
        # shipped = zero pending, has completed tasks
        shipped, in_progress, next_phase, future = [], [], [], []
        for name, data in plans.items():
            if data["pending"] == 0 and data["completed"] > 0:
                shipped.append(name)
            elif data["pending"] > 0 and data["active"] > 0:
                in_progress.append(name)
            elif data["pending"] > 0:
                next_phase.append(name)
            else:
                future.append(name)

        # Present projection
        print(f"\n══ ROADMAP INIT: {project_id} ══")
        print(f"\nDiscovered {len(plans)} plans. Proposed phases:\n")
        print(
            f"  shipped     ({len(shipped)}): {', '.join(shipped[:5])}"
            f"{'...' if len(shipped) > 5 else ''}"
        )
        print(
            f"  in-progress ({len(in_progress)}): {', '.join(in_progress[:5])}"
            f"{'...' if len(in_progress) > 5 else ''}"
        )
        print(
            f"  next        ({len(next_phase)}): {', '.join(next_phase[:5])}"
            f"{'...' if len(next_phase) > 5 else ''}"
        )
        print(
            f"  future      ({len(future)}): {', '.join(future[:5])}"
            f"{'...' if len(future) > 5 else ''}"
        )
        print(
            "\nThis creates a ledger plan. Adjust phases after with "
            "'tw-flow roadmap add'."
        )
        print("Proceed? [y/N] ", end="", flush=True)
        confirm = input().strip().lower()
        if confirm != "y":
            self.info("Aborted.")
            return

        # Create roadmap plan with one root task per active/future ini
        # Shipped inis are recorded as completed phases
        def add_phase(desc: str, phase: str, ini: str):
            self.tw.run(
                ["add", f"project:{roadmap_plan}", desc],
                capture=True,
            )
            # Extract UUID from output "Created task N." then fetch it
            new_tasks = self.tw.export(
                [
                    f'project:"{roadmap_plan}"',
                    "status:pending",
                    f"description:{desc}",
                ]
            )
            if new_tasks:
                uuid = new_tasks[-1]["uuid"]
                self.tw.run(
                    [
                        uuid,
                        "modify",
                        f"phase:{phase}",
                        f"operational_ini:{ini}",
                    ]
                )

        for name in in_progress:
            add_phase(name, "in-progress", name)
        for name in next_phase:
            add_phase(name, "next", name)
        for name in future:
            add_phase(name, "future", name)
        for name in shipped:
            add_phase(name, "shipped", name)
            # Mark shipped phases as done in Taskwarrior
            done_tasks = self.tw.export(
                [
                    f'project:"{roadmap_plan}"',
                    "status:pending",
                    f"description:{name}",
                ]
            )
            if done_tasks:
                self.tw.run([done_tasks[-1]["uuid"], "done"])
        self.success(
            f"Roadmap initialized: {roadmap_plan} "
            f"({len(in_progress)} in-progress + {len(next_phase)} next + "
            f"{len(future)} future + {len(shipped)} shipped phases)."
        )

    def cmd_roadmap_add(self, phase: str, description: str, ini: str = ""):
        """Add a phase to the roadmap ledger."""
        valid_phases = {
            "shipped",
            "in-progress",
            "next",
            "blocked",
            "future",
            "cancelled",
        }
        if phase not in valid_phases:
            self.error(
                f"Invalid phase '{phase}'. "
                f"Valid: {', '.join(sorted(valid_phases))}"
            )
            return
        project_id = os.environ.get("PROJECT_ID", "")
        roadmap_plan = f"{project_id}-roadmap"
        args = [
            "add",
            f"project:{roadmap_plan}",
            f"phase:{phase}",
            description,
        ]
        if ini:
            args.append(f"operational_ini:{ini}")
        self.tw.run(args)
        ini_str = f" → {ini}" if ini else ""
        self.success(f"Phase added: [{phase}] {description}{ini_str}")

    def cmd_ship(self, uuid: str):
        """Mark a roadmap phase as shipped."""
        tasks = self.tw.export([uuid, "status:pending"])
        if not tasks:
            self.error(f"Task not found or already completed: {uuid}")
            return
        t = tasks[0]
        if not t.get("project", "").endswith("-roadmap"):
            self.error(
                "Only roadmap phase tasks can be shipped. "
                "Use 'tw-flow done' for operational tasks."
            )
            return
        self.tw.run([uuid, "modify", "phase:shipped"])
        self.success(f"Phase shipped: {t.get('description', uuid)[:60]} ✓")

    def cmd_session_list(self):
        """List all independent sessions with mtime-based status."""
        import glob
        import time

        data_dir = self.focus.data_dir
        session_files = sorted(
            glob.glob(os.path.join(data_dir, "focus-*.json")),
            key=os.path.getmtime,
            reverse=True,
        )

        if not session_files:
            self.info("No independent sessions found.")
            return

        current_session_id = os.environ.get("JACAZUL_SESSION_ID", "")
        now = time.time()

        print(
            "SESSION ID   PLAN                           TASK       "
            "AGE     STATUS"
        )
        print("-" * 72)
        for f in session_files:
            fname = os.path.basename(f)
            session_id = fname.removeprefix("focus-").removesuffix(".json")
            mtime = os.path.getmtime(f)
            age_seconds = now - mtime

            if age_seconds < 7200:
                status = "active"
            elif age_seconds < 28800:
                status = "idle"
            else:
                status = "orphan"

            if age_seconds < 60:
                age_str = f"{int(age_seconds)}s"
            elif age_seconds < 3600:
                age_str = f"{int(age_seconds // 60)}m"
            elif age_seconds < 86400:
                age_str = f"{int(age_seconds // 3600)}h"
            else:
                age_str = f"{int(age_seconds // 86400)}d"

            try:
                with open(f, "rb") as fh:
                    data = orjson.loads(fh.read())
                plan = data.get("focused_plan") or "-"
                task_uuid = data.get("focused_task_uuid") or "-"
                task_short = task_uuid[:8] if task_uuid != "-" else "-"
            except Exception:
                plan = "?"
                task_short = "?"

            marker = "*" if session_id == current_session_id else " "
            print(
                f"{session_id} {marker}  {plan:<30} {task_short:<10} {
                    age_str:<7} {status}"
            )

    def cmd_session_purge(self, confirm: bool = False):
        """Remove orphan session files (mtime > 8h)."""
        import glob
        import time

        data_dir = self.focus.data_dir
        current_session_id = os.environ.get("JACAZUL_SESSION_ID", "")
        now = time.time()

        session_files = glob.glob(os.path.join(data_dir, "focus-*.json"))
        orphans = []
        for f in session_files:
            session_id = (
                os.path.basename(f)
                .removeprefix("focus-")
                .removesuffix(".json")
            )
            if session_id == current_session_id:
                continue
            age_seconds = now - os.path.getmtime(f)
            if age_seconds >= 28800:
                orphans.append(session_id)

        if not orphans:
            self.info("No orphan sessions to purge.")
            return

        print(f"Orphan sessions ({len(orphans)}):")
        for sid in orphans:
            note = os.path.join(data_dir, f"session-note-{sid}.md")
            has_note = " + note" if os.path.exists(note) else ""
            print(f"  {sid}{has_note}")

        if not confirm:
            print("")
            self.info("Dry run. Use --confirm to delete.")
            return

        for sid in orphans:
            focus_file = os.path.join(data_dir, f"focus-{sid}.json")
            note_file = os.path.join(data_dir, f"session-note-{sid}.md")
            os.remove(focus_file)
            if os.path.exists(note_file):
                os.remove(note_file)

        self.success(f"Purged {len(orphans)} orphan session(s).")

    def cmd_session_ack(self):
        """Acknowledge session handoff note.

        Marks it as read and dismisses the status banner.
        """
        from datetime import datetime, timezone

        session_id = os.environ.get("JACAZUL_SESSION_ID", "global")
        note_path = os.path.join(
            self.focus.data_dir,
            f"session-note-{session_id}.md",
        )
        if not os.path.exists(note_path):
            self.info("No session note found.")
            return
        with open(note_path) as f:
            content = f.read()
        if "acknowledged:" in content:
            self.info("Session note already acknowledged.")
            return
        ts = datetime.now(timezone.utc).isoformat()
        with open(note_path, "a") as f:
            f.write(f"\nacknowledged: {ts}\n")
        self.success("Session note acknowledged. Context loaded.")

    def cmd_session_resume(self):
        """Print a pending handoff or report an acknowledged note."""
        session_id = os.environ.get("JACAZUL_SESSION_ID", "global")
        note_path = os.path.join(
            self.focus.data_dir,
            f"session-note-{session_id}.md",
        )
        if not os.path.exists(note_path):
            return
        with open(note_path) as f:
            content = f.read()
        if "acknowledged:" in content:
            self.info(
                f"Session note already acknowledged: {note_path}. "
                "Context will not be replayed."
            )
            return
        print(f"📋 SESSION HANDOFF — {note_path}")
        print("")
        print(content)

    def cmd_session_dump(self, force: bool = False):
        """Generate introspective handoff note for the current session."""
        import subprocess as sp
        from datetime import datetime, timezone

        session_id = os.environ.get("JACAZUL_SESSION_ID", "global")
        state = self.focus.load()
        plan = state.focused_plan or ""
        task_uuid = state.focused_task_uuid or ""

        lines = []
        lines.append("# Session Handoff Note")
        lines.append(
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        )
        lines.append(f"**Session:** {session_id}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Focus state
        lines.append("## Current Focus")
        lines.append("")
        if plan:
            lines.append(f"**Plan:** `{plan}`")
        if task_uuid:
            tasks = self.tw.export([task_uuid[:8]])
            desc = (
                tasks[0].get("description", task_uuid) if tasks else task_uuid
            )
            lines.append(f"**Anchor:** `{task_uuid[:8]}` {desc}")
        lines.append("")
        lines.append("Restore focus:")
        lines.append("```bash")
        if task_uuid:
            lines.append(f"tw-flow focus ind task {task_uuid[:8]}")
        elif plan:
            lines.append(f"tw-flow focus ind plan {plan}")
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Inherited context from focused task
        if task_uuid:
            tasks = self.tw.export([task_uuid[:8]])
            if tasks:
                t = tasks[0]
                annotations = t.get("annotations", [])
                decisions = [
                    a["description"]
                    for a in annotations
                    if a.get("description", "").startswith("DECISION:")
                    or a.get("description", "").startswith("OUTCOME:")
                    or a.get("description", "").startswith("RESEARCH:")
                ]
                if decisions:
                    lines.append("## Inherited Context")
                    lines.append("")
                    for d in decisions[-5:]:  # last 5 most relevant
                        lines.append(f"- {d}")
                    lines.append("")
                    lines.append("---")
                    lines.append("")

        # Pending tasks in plan
        if plan:
            pending = self.tw.export([f'project:"{plan}"', "status:pending"])
            if pending:
                lines.append("## Pending Tasks in Plan")
                lines.append("")
                lines.append("| UUID | Description |")
                lines.append("|---|---|")
                for t in pending:
                    lines.append(
                        f"| `{t['uuid'][:8]}` | {t.get('description', '?')} |"
                    )
                lines.append("")
                lines.append("---")
                lines.append("")

        # Git diff --stat
        git_result = sp.run(
            ["git", "diff", "--stat", "HEAD"],
            capture_output=True,
            text=True,
        )
        if git_result.stdout.strip():
            lines.append("## Uncommitted Changes")
            lines.append("")
            lines.append("```")
            lines.append(git_result.stdout.strip())
            lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Introspective prompt template
        lines.append("## Session Notes")
        lines.append("")
        lines.append("<!-- FILL IN -->")
        lines.append("")

        content = "\n".join(lines)

        # Write to session note file
        output_path = os.path.join(
            self.focus.data_dir,
            f"session-note-{session_id}.md",
        )

        if not force and os.path.exists(output_path):
            with open(output_path) as f:
                existing = f.read()
            if "<!-- FILL IN -->" in existing:
                self.error(
                    f"Session note already exists: {output_path}\n"
                    "It has an unfilled section. You created this already — "
                    "fill it in, don't regenerate.\n"
                    "Use --force to overwrite."
                )
            elif "acknowledged:" in existing:
                self.error(
                    f"Session note already exists: {output_path}\n"
                    "This note is already acknowledged by the "
                    "acknowledged: marker and contains previous session "
                    "context. READ IT FIRST — it has the context you are "
                    "missing right now.\n"
                    "Use --force to overwrite."
                )
            elif "injected:" in existing:
                self.error(
                    f"Session note already exists: {output_path}\n"
                    "This note was injected but is not acknowledged; the "
                    "injected: marker records delivery only. READ IT FIRST "
                    "and acknowledge it before replacing it.\n"
                    "Use --force to overwrite."
                )
            else:
                self.error(
                    f"Session note already exists: {output_path}\n"
                    "This note was written by a previous agent and "
                    "already has content. READ IT FIRST — it has the "
                    "context you are missing right now.\n"
                    "Use --force to overwrite."
                )
            return

        with open(output_path, "w") as f:
            f.write(content)

        self.success(f"Session dump written: {output_path}")
        print("")
        print(content)

    def cmd_plans(
        self,
        show_all: bool = False,
        show_closed: bool = False,
        with_backlog: bool = False,
    ):
        self.info("Project Plans Landscape:")
        print("")

        # Fetch all relevant tasks
        filter_args = [] if show_all or show_closed else ["status:pending"]
        all_tasks = self.tw.export(filter_args)

        # Group tasks by project
        projects = {}
        for t in all_tasks:
            plan = t.get("project")
            if not plan or "_archive" in plan or "_trash" in plan:
                continue
            if plan not in projects:
                projects[plan] = {
                    "pending": 0,
                    "active": 0,
                    "completed": 0,
                    "blocked": 0,
                    "backlog": False,
                }

            if t["status"] == "pending":
                projects[plan]["pending"] += 1
                if t.get("start"):
                    projects[plan]["active"] += 1
                if t.get("tags") and "BLOCKED" in t["tags"]:
                    projects[plan]["blocked"] += 1
                if t.get("backlog") and int(t.get("backlog", 0)) == 1:
                    projects[plan]["backlog"] = True
            elif t["status"] == "completed":
                projects[plan]["completed"] += 1

        # Determine which projects to show
        plans = sorted(projects.keys())
        displayed = 0

        for plan in plans:
            p = projects[plan]
            is_open = p["pending"] > 0
            is_backlog = p["backlog"]

            # Skip backlog plans unless --with-backlog or --all
            if is_backlog and not with_backlog and not show_all:
                continue

            if show_all:
                should_show = True
            elif show_closed:
                should_show = not is_open
            else:
                should_show = is_open

            if should_show:
                if is_backlog:
                    icon = "💤"
                    status_label = "BACKLOG"
                else:
                    icon = "●" if is_open else "✓"
                    status_label = "ACTIVE" if is_open else "ZEROED"
                print(f"{icon} {plan} [{status_label}]")
                print(
                    f"  Pending: {p['pending']} | Active: {p['active']} | "
                    f"Completed: {p['completed']} | Blocked: {p['blocked']}\n"
                )

                displayed += 1

        if displayed == 0:
            self.success("No plans match the filter!")

    def cmd_ponder(self, args: List[str]):
        from jacazul.cli.ponder import Dashboard

        show_all = "--all" in args
        use_table = "--table" in args
        with_backlog = "--with-backlog" in args
        project_root = next((a for a in args if not a.startswith("-")), None)
        db = Dashboard(
            project_root,
            show_all,
            hide_tip=True,
            use_table=use_table,
            with_backlog=with_backlog,
        )
        db.render()

    def cmd_active(self):
        self.info("Currently active tasks:")
        print("")
        self.tw.run(["+ACTIVE"], capture=False)

    def cmd_blocked(self):
        self.info("Blocked tasks:")
        print("")
        self.tw.run(["+BLOCKED"], capture=False)

    def cmd_overdue(self):
        self.info("Overdue tasks:")
        print("")
        self.tw.run(["due.before:today", "status:pending"], capture=False)

    def cmd_urgent(self, input_id: str, urgency: str = "15.0"):
        uuid = self.resolve_uuid(input_id)
        self.tw.run([uuid, "modify", f"urgency:{urgency}", "priority:H"])
        self.success(f"Task {uuid[:8]} marked as urgent (urgency: {urgency})")

    def cmd_block(self, input_id: str, dep_id: str):
        uuid, dep_uuid = self.resolve_uuid(input_id), self.resolve_uuid(dep_id)
        self.tw.run([uuid, "modify", f"depends:{dep_uuid}"])
        self.success(f"Task {uuid[:8]} now depends on task {dep_uuid[:8]}")

    def cmd_unblock(self, input_id: str, dep_id: str):
        uuid, dep_uuid = self.resolve_uuid(input_id), self.resolve_uuid(dep_id)
        tasks = self.tw.export([uuid])
        if not tasks:
            return
        new_deps = [
            d for t in tasks for d in t.get("depends", []) if d != dep_uuid
        ]
        self.tw.run(
            [
                uuid,
                "modify",
                f"depends:{','.join(new_deps)}" if new_deps else "depends:",
            ]
        )
        self.success(
            f"Removed dependency on task {dep_uuid[:8]} from task {uuid[:8]}"
        )

    def cmd_wait(self, input_id: str, date: str):
        uuid = self.resolve_uuid(input_id)
        self.tw.run([uuid, "modify", f"wait:{date}"])
        self.success(f"Task {uuid[:8]} waiting until {date}")

    def cmd_discard(self, input_id: str):
        uuid = self.resolve_uuid(input_id)
        tasks = self.tw.export([uuid])
        if not tasks:
            return
        ini = tasks[0].get("project", "unscoped")
        archive = f"{ini.split(':_archive')[0]}:_archive"
        os.environ["TW_FLOW_INTERNAL"] = "true"
        self.tw.run([uuid, "modify", f'project:"{archive}"', "+DISCARDED"])
        self.annotate(uuid, "OUTCOME", "Task discarded and moved to archive.")
        self.tw.run([uuid, "done"])
        self.success(f"Task {uuid[:8]} moved to archive and marked done.")

    def cmd_tree(self, filter_val: str = "status:pending"):
        plan = (
            filter_val
            if "project:" in filter_val or "status:" in filter_val
            else f'project:"{filter_val}"'
        )
        print(f"══ Plan: {filter_val} ══")

        def render(uuid, indent="", last=True):
            tasks = self.tw.export([uuid])
            if not tasks:
                return
            t = tasks[0]
            icon = (
                "✓"
                if t["status"] == "completed"
                else (
                    "⚡"
                    if t.get("start")
                    else (
                        "🔒"
                        if "READY"
                        not in self.tw.run(
                            [uuid, "+READY"], capture=True
                        ).stdout
                        else "○"
                    )
                )
            )
            marker = ("└── " if last else "├── ") if indent else ""
            print(f"{indent}{marker}{icon} ({uuid[:8]}) | {t['description']}")
            children = [
                c["uuid"]
                for c in self.tw.export(
                    [f"depends.contains:{uuid}"]
                )
                if "_archive" not in c.get("project", "")
            ]
            for i, c_uuid in enumerate(children):
                render(
                    c_uuid,
                    indent + ("    " if last else "│   "),
                    i == len(children) - 1,
                )

        roots = [
            t["uuid"]
            for t in self.tw.export([plan])
            if not t.get("depends") and "_archive" not in t.get("project", "")
        ]
        for uuid in roots:
            render(uuid)


def main():
    if len(sys.argv) < 2:
        print(f"tw-flow v{VERSION}")
        sys.exit(0)
    cmd, args, flow = sys.argv[1], sys.argv[2:], FlowManager()
    if cmd in ["plan", "initiative", "ini"]:
        flow.cmd_plan(args[0], args[1:])
        flow.cache.bust()
    elif cmd == "status":
        pending_only = "--pending" in args
        use_table = "--table" in args
        force = "--force" in args
        filter_val = next((a for a in args if not a.startswith("-")), None)
        cache_key = f"status_{filter_val}" if filter_val else "status"
        if not force and not pending_only and not use_table:
            cached = flow.cache.get(cache_key, CacheManager.STATUS_TTL)
            if cached is not None:
                print("🐊 [cached] Status unchanged. Use --force to refresh.")
                sys.exit(0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            flow.cmd_status(filter_val, pending_only, use_table)
        output = buf.getvalue()
        sys.stdout.write(output)
        if not pending_only and not use_table:
            flow.cache.set(cache_key, output)
    elif cmd == "ponder":
        force = "--force" in args
        ponder_args = [a for a in args if a != "--force"]
        project_root = next(
            (a for a in ponder_args if not a.startswith("-")), None
        )
        cache_key = f"ponder_{project_root}" if project_root else "ponder"
        if not force:
            cached = flow.cache.get(cache_key, CacheManager.PONDER_TTL)
            if cached is not None:
                print("🐊 [cached] Ponder unchanged. Use --force to refresh.")
                sys.exit(0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            flow.cmd_ponder(ponder_args)
        output = buf.getvalue()
        sys.stdout.write(output)
        flow.cache.set(cache_key, output)
    elif cmd == "next":
        flow.cmd_next(args[0] if args else "status:pending")
    elif cmd == "execute":
        _tasks = flow.tw.export([flow.resolve_uuid(args[0])])
        _ini = _tasks[0].get("project") if _tasks else None
        flow.cmd_execute(args[0])
        flow.cache.bust(ini_name=_ini)
    elif cmd == "done":
        _tasks = flow.tw.export([flow.resolve_uuid(args[0])])
        _ini = _tasks[0].get("project") if _tasks else None
        flow.cmd_done(args[0], args[1] if len(args) > 1 else None)
        flow.cache.bust(ini_name=_ini)
    elif cmd == "outcome":
        _tasks = flow.tw.export([flow.resolve_uuid(args[0])])
        _ini = _tasks[0].get("project") if _tasks else None
        flow.cmd_outcome(args[0], " ".join(args[1:]))
        flow.cache.bust(ini_name=_ini)
    elif cmd == "handoff":
        flow.cmd_handoff(args[0], " ".join(args[1:]))
        flow.invalidate_task_cache(args[0])
    elif cmd == "reopen":
        flow.cmd_reopen(args[0])
        flow.invalidate_task_cache(args[0])
    elif cmd == "amend":
        flow.cmd_amend(args[0], args[1:])
        flow.invalidate_task_cache(args[0])
    elif cmd == "notes":
        flow.cmd_notes(args[0])
    elif cmd == "note":
        _tasks = flow.tw.export([flow.resolve_uuid(args[0])])
        _ini = _tasks[0].get("project") if _tasks else None
        flow.cmd_note(args[0], args[1], " ".join(args[2:]))
        flow.cache.bust(ini_name=_ini)
    elif cmd == "ticket":
        flow.cmd_ticket(args[0], args[1])
        flow.invalidate_task_cache(args[0])
    elif cmd == "e2e":
        if not args:
            flow.error(
                "Missing plan name.\n   ACTION: tw-flow e2e <plan>, after "
                "the operator approved the initiative's contract."
            )
        flow.cmd_e2e(args[0])
        flow.cache.bust(ini_name=args[0])
    elif cmd == "commit":
        flow.cmd_commit(is_fix="--fix" in args)
    elif cmd == "context":
        flow.cmd_context(args[0])
    elif cmd == "backlog":
        if not args:
            flow.error("Usage: tw-flow backlog <plan-name>")
        flow.cmd_backlog(args[0])
        flow.cache.bust()
    elif cmd == "activate":
        if not args:
            flow.error("Usage: tw-flow activate <plan-name>")
        flow.cmd_activate(args[0])
        flow.cache.bust()
    elif cmd in ["plans", "inis", "initiatives"]:
        if "--help" in args:
            print(
                "Usage: tw-flow plans"
                " [--all|--closed|--with-backlog] [--force]\n"
                "  (no flags)      Show active plans only\n"
                "  --all           Show all plans (active + closed)\n"
                "  --closed        Show closed (zeroed) plans only\n"
                "  --with-backlog  Include backlog plans (marked 💤)\n"
                "  --force         Bypass cache and fetch fresh data"
            )
            sys.exit(0)
        show_all = "--all" in args
        show_closed = "--closed" in args
        with_backlog = "--with-backlog" in args
        force = "--force" in args
        if show_all:
            cache_key = "plans_all"
        elif show_closed:
            cache_key = "plans_closed"
        elif with_backlog:
            cache_key = "plans_with_backlog"
        else:
            cache_key = "plans"
        if not force:
            cached = flow.cache.get(cache_key, CacheManager.PLANS_TTL)
            if cached is not None:
                print("🐊 [cached] Plans unchanged. Use --force to refresh.")
                sys.exit(0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            flow.cmd_plans(show_all, show_closed, with_backlog)
        output = buf.getvalue()
        sys.stdout.write(output)
        flow.cache.set(cache_key, output)
    elif cmd == "active":
        flow.cmd_active()
    elif cmd == "blocked":
        flow.cmd_blocked()
    elif cmd == "overdue":
        flow.cmd_overdue()
    elif cmd == "urgent":
        flow.cmd_urgent(args[0], args[1] if len(args) > 1 else "15.0")
        flow.invalidate_task_cache(args[0])
    elif cmd == "block":
        flow.cmd_block(args[0], args[1])
        flow.invalidate_task_cache(args[0])
    elif cmd == "unblock":
        flow.cmd_unblock(args[0], args[1])
        flow.invalidate_task_cache(args[0])
    elif cmd == "wait":
        flow.cmd_wait(args[0], args[1])
        flow.invalidate_task_cache(args[0])
    elif cmd == "discard":
        flow.cmd_discard(args[0])
        flow.cache.bust()
    elif cmd == "rename":
        if len(args) < 2:
            flow.error("Usage: tw-flow rename <old_name> <new_name>")
        flow.cmd_rename(args[0], args[1])
    elif cmd == "session":
        sub = args[0] if args else None
        if sub == "list":
            flow.cmd_session_list()
        elif sub == "dump":
            force = "--force" in args
            flow.cmd_session_dump(force=force)
        elif sub == "resume":
            flow.cmd_session_resume()
        elif sub == "ack":
            flow.cmd_session_ack()
        elif sub == "purge":
            confirm = "--confirm" in args
            flow.cmd_session_purge(confirm=confirm)
        else:
            flow.error(
                "Usage: tw-flow session <subcommand>\n"
                "   ACTION: Available subcommands: list, dump, resume, "
                "ack, purge"
            )
    elif cmd == "roadmap":
        sub = args[0] if args else None
        if sub == "init":
            flow.cmd_roadmap_init()
        elif sub == "add":
            if len(args) < 3:
                flow.error(
                    "Usage: tw-flow roadmap add <phase> <description>"
                    " [--ini <plan>]"
                )
            ini = ""
            if "--ini" in args:
                ini_idx = args.index("--ini")
                ini = args[ini_idx + 1] if ini_idx + 1 < len(args) else ""
            flow.cmd_roadmap_add(args[1], args[2], ini)
        else:
            flow.cmd_roadmap()
    elif cmd == "ship":
        if not args:
            flow.error("Usage: tw-flow ship <phase-uuid>")
        flow.cmd_ship(args[0])
    elif cmd == "tree":
        flow.cmd_tree(args[0] if args else "status:pending")
    elif cmd == "focus":
        sub = args[0] if args else None
        if sub == "ind":
            ind_sub = args[1] if len(args) > 1 else None
            if ind_sub in ["plan", "ini"]:
                name = (
                    args[2]
                    if len(args) > 2
                    else (
                        flow.tw.export(["+ACTIVE"])[0].get("project")
                        if flow.tw.export(["+ACTIVE"])
                        else None
                    )
                )
                if name:
                    flow.focus.update_plan(name)
                    tasks = flow.tw.export(
                        [f'project:"{name}"', "status:pending", "limit:1"]
                    )
                    if tasks:
                        flow.focus.push_task(tasks[0]["uuid"], name)
                        flow.success(
                            f"Independent focus anchored to plan: {name} "
                            f"(Task pushed to heap: {tasks[0]['uuid'][:8]})"
                        )
                    else:
                        flow.success(
                            f"Independent focus anchored to plan: {name}"
                        )
                else:
                    flow.error("Plan name required")
            elif ind_sub == "task":
                uuid = flow.resolve_uuid(args[2]) if len(args) > 2 else None
                tasks = flow.tw.export([uuid]) if uuid else []
                if tasks:
                    flow.focus.push_task(uuid, tasks[0].get("project", ""))
                    flow.success(
                        f"Independent focus anchored to task: {uuid[:8]} "
                        f"(pushed to stack)"
                    )
                else:
                    flow.error("Usage: focus ind task <uuid>")
            elif ind_sub:
                tasks = flow.tw.export([f'project:"{ind_sub}"', "limit:1"])
                if tasks:
                    name = tasks[0]["project"]
                    flow.focus.update_plan(name)
                    pending = flow.tw.export(
                        [f'project:"{name}"', "status:pending", "limit:1"]
                    )
                    if pending:
                        flow.focus.push_task(pending[0]["uuid"], name)
                        flow.success(
                            f"Independent smart-focus anchored to: {name} "
                            f"(Task: {pending[0]['uuid'][:8]})"
                        )
                    else:
                        flow.success(
                            f"Independent smart-focus anchored to: {name}"
                        )
                else:
                    flow.error(
                        f"Unknown plan or smart-focus: '{ind_sub}'.\n"
                        "   ACTION: Use 'focus ind plan <name>', "
                        "'focus ind task <uuid>', or 'focus ind <plan-name>'."
                    )
            else:
                flow.error(
                    "Usage: focus ind [plan <name>|task <uuid>|<plan-name>]"
                )
        elif sub == "back":
            session_file = flow.focus.session_file_path
            if session_file and os.path.exists(session_file):
                os.remove(session_file)
                flow.cache.bust(focus_change=True)
                flow.success(
                    "Exited independent session. "
                    "Switched back to global focus."
                )
            else:
                flow.error(
                    "No independent session active. Already in global mode."
                )
        elif sub in ["plan", "ini"]:
            name = (
                args[1]
                if len(args) > 1
                else (
                    flow.tw.export(["+ACTIVE"])[0].get("project")
                    if flow.tw.export(["+ACTIVE"])
                    else None
                )
            )
            if name:
                flow.focus.update_plan(name)
                flow.cache.bust(ini_name=name)
                tasks = flow.tw.export(
                    [f'project:"{name}"', "status:pending", "limit:1"]
                )
                if tasks:
                    flow.focus.push_task(tasks[0]["uuid"], name)
                    flow.success(
                        f"Focused plan anchored to: {name} "
                        f"(Task pushed to heap: {tasks[0]['uuid'][:8]})"
                    )
                else:
                    flow.success(f"Focused plan anchored to: {name}")
            else:
                flow.error("Plan name required")
        elif sub == "task":
            uuid = flow.resolve_uuid(args[1])
            tasks = flow.tw.export([uuid])
            if tasks:
                flow.focus.push_task(uuid, tasks[0].get("project", ""))
                flow.cache.bust(focus_change=True)
                flow.success(
                    f"Focused task anchored to: {uuid[:8]} (pushed to stack)"
                )
        elif sub == "pop":
            flow.focus.pop_task()
            flow.success(
                f"Popped task focus. Current top: "
                f"{flow.focus.load().focused_task_uuid or 'none'}"
            )
        elif sub == "interest":
            action, name = (
                (args[1] if len(args) > 1 else None),
                (args[2] if len(args) > 2 else None),
            )
            state = flow.focus.load()
            if action == "add" and name:
                state.plans_of_interest = sorted(
                    list(set(state.plans_of_interest + [name]))
                )
                flow.focus.save(state)
                flow.success(f"Added '{name}' to interests.")
            elif action == "remove" and name:
                state.plans_of_interest = [
                    i for i in state.plans_of_interest if i != name
                ]
                flow.focus.save(state)
                flow.success(f"Removed '{name}' from interests.")
            elif action == "list":
                print(
                    "══ Plans of Interest ══\n"
                    + (
                        "\n".join(state.plans_of_interest)
                        if state.plans_of_interest
                        else "(empty)"
                    )
                )
            else:
                flow.error("Usage: focus interest [add|remove|list] <name>")
        elif sub == "clear":
            state = flow.focus.load()
            state.focused_plan = None
            state.focused_task_uuid = None
            state.task_track = []
            flow.focus.save(state)
            flow.success("Focus cleared (plan and task anchors reset).")
        elif sub:
            # Smart Focus: Check if 'sub' is a valid plan name
            tasks = flow.tw.export([f'project:"{sub}"', "limit:1"])
            if tasks:
                name = tasks[0]["project"]
                flow.focus.update_plan(name)
                flow.cache.bust(focus_change=True)
                pending = flow.tw.export(
                    [f'project:"{name}"', "status:pending", "limit:1"]
                )
                if pending:
                    flow.focus.push_task(pending[0]["uuid"], name)
                    flow.success(
                        f"Smart-focused anchored to: {name} "
                        f"(Task: {pending[0]['uuid'][:8]})"
                    )
                else:
                    flow.success(f"Smart-focused anchored to: {name}")
            else:
                flow.error(
                    f"Unknown focus subcommand or plan: '{sub}'.\n"
                    "   ACTION: Use 'focus plan <name>'"
                    " or 'focus task <uuid>'."
                )
        else:
            print(
                "══ Current Session Focus ══\n"
                + orjson.dumps(
                    flow.focus.load().to_dict(), option=orjson.OPT_INDENT_2
                ).decode()
            )
        flow.cache.bust(focus_change=True)
    elif cmd == "cache":
        sub = args[0] if args else "info"
        if sub == "clear":
            scope = args[1] if len(args) > 1 else None
            flow.cache.clear(scope)
            label = scope or "all"
            flow.success(f"Cache cleared: {label}")
        elif sub == "info":
            info = flow.cache.info()
            print(f"🐊 Cache: {info['files']} file(s) in {info['dir']}")
        else:
            flow.error("Usage: tw-flow cache [clear [status|ponder]|info]")
    elif cmd in ["help", "--help", "-h"]:
        print(
            "tw-flow USAGE:\n"
            "  plan <plan> <tasks...>\n"
            "  next [plan]\n"
            "  execute <id>\n"
            "  done <id> [note]\n"
            "  outcome <id> <msg>\n"
            "  reopen <id>\n"
            '  amend <id> [description="..."] [ticket="..."]\n'
            "  note <id> <type> <msg>\n"
            "  ticket <id> <ticket>\n"
            "  e2e <plan>\n"
            "  commit [--fix]\n"
            "  discard <id>\n"
            "  rename <old> <new>\n"
            "  plans [--all|--closed] | "
            "status [plan] [--pending] [--table] [--force]\n"
            "  ponder [project_root] [--all] [--force]\n"
            "  cache [clear [status|ponder]|info]\n"
            "  focus [plan|task|pop|interest|clear]\n"
            "  tree [plan]\n"
            "  roadmap [init|add <phase> <desc> [--ini <plan>]]\n"
            "  session [list|dump]"
        )
    else:
        flow.error(f"Unknown command: {cmd}")

    # Heartbeat: touch active session file on every command execution
    session_file = flow.focus.session_file_path
    if session_file and os.path.exists(session_file):
        os.utime(session_file, None)


if __name__ == "__main__":
    main()
