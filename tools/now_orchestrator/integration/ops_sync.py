from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Callable

from .coordinator import Runner, subprocess_runner
from .provenance import ProvenanceJournal

_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
_HEAD = re.compile(r"[0-9a-f]{40,64}\Z")


@dataclass(frozen=True)
class FileUpdate:
    path: str
    content: str


@dataclass(frozen=True)
class OpsSyncInput:
    repo_root: Path
    repo: str
    base_ref: str
    branch: str
    task_key: str
    dispatch_id: str
    issue_key: str
    scope_digest: str
    product_merge_commit: str
    exec_plan_path: str
    updates: tuple[FileUpdate, ...]
    commit_message: str
    pr_title: str
    pr_body: str
    approval_id: str
    approval_digest: str


@dataclass(frozen=True)
class OpsSyncReadback:
    worktree: str
    branch: str
    head: str
    pr_number: int
    pr_state: str
    pr_url: str
    operation_id: str
    request_digest: str
    merge_commit: str | None
    repo: str
    base_ref: str
    task_key: str
    dispatch_id: str
    issue_key: str
    scope_digest: str
    product_merge_commit: str
    handoff_blob: str
    tasks_blob: str
    exec_plan_path: str
    exec_plan_blob: str


@dataclass(frozen=True)
class OpsApprovalReadback:
    approval_id: str
    request_digest: str
    approver: str
    source_ref: str


OpsApprovalPort = Callable[[str], OpsApprovalReadback]


def _request_digest(request: OpsSyncInput) -> str:
    payload = {
        "repo_root": str(request.repo_root.resolve()),
        "repo": request.repo,
        "base_ref": request.base_ref,
        "branch": request.branch,
        "task_key": request.task_key,
        "dispatch_id": request.dispatch_id,
        "issue_key": request.issue_key,
        "scope_digest": request.scope_digest,
        "product_merge_commit": request.product_merge_commit,
        "exec_plan_path": request.exec_plan_path,
        "updates": [{"path": item.path, "content_digest": sha256(item.content.encode()).hexdigest()} for item in request.updates],
        "commit_message": request.commit_message,
        "pr_title": request.pr_title,
        "pr_body_digest": sha256(request.pr_body.encode()).hexdigest(),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _safe_write(root: Path, relative: str, content: str) -> None:
    parts = PurePosixPath(relative).parts
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    current_fd = root_fd
    try:
        for part in parts[:-1]:
            try:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current_fd)
            except FileNotFoundError:
                os.mkdir(part, 0o755, dir_fd=current_fd)
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current_fd)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        descriptor = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644, dir_fd=current_fd)
        try:
            payload = content.encode()
            offset = 0
            while offset < len(payload):
                written = os.write(descriptor, payload[offset:])
                if written <= 0:
                    raise OSError("short ops sync write")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)


def _safe_read(root: Path, relative: str) -> str:
    parts = PurePosixPath(relative).parts
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    current_fd = root_fd
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current_fd)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=current_fd)
        try:
            return os.read(descriptor, os.fstat(descriptor).st_size).decode("utf-8")
        finally:
            os.close(descriptor)
    finally:
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)


class OpsRepoSync:
    def __init__(self, runner: Runner = subprocess_runner, path_factory: Callable[[str], Path] | None = None, approval_authority: OpsApprovalPort | None = None) -> None:
        self.runner = runner
        self.path_factory = path_factory or (lambda digest: Path(tempfile.gettempdir()) / f"proxima-now-ops-{digest[:24]}")
        self.approval_authority = approval_authority

    @staticmethod
    def _validate(request: OpsSyncInput) -> tuple[str, ...]:
        required = (request.repo, request.base_ref, request.branch, request.task_key, request.dispatch_id, request.issue_key, request.scope_digest, request.product_merge_commit, request.exec_plan_path, request.commit_message, request.pr_title, request.pr_body, request.approval_id, request.approval_digest)
        if not request.updates or not all(isinstance(value, str) and value for value in required):
            raise ValueError("ops sync input is incomplete")
        if not _HEAD.fullmatch(request.scope_digest) or not _HEAD.fullmatch(request.product_merge_commit):
            raise ValueError("ops sync identity digest/commit is invalid")
        if not _REF.fullmatch(request.base_ref) or not _REF.fullmatch(request.branch) or ".." in request.base_ref.split("/") or ".." in request.branch.split("/"):
            raise ValueError("ops sync Git ref is unsafe")
        paths: list[str] = []
        for update in request.updates:
            pure = PurePosixPath(update.path)
            if not isinstance(update.content, str) or pure.is_absolute() or ".." in pure.parts or str(pure) in {"", "."} or any(mark in update.path for mark in "*?["):
                raise ValueError("ops sync path is unsafe")
            canonical = str(pure)
            if canonical in paths:
                raise ValueError("ops sync path is duplicated")
            paths.append(canonical)
        canonical_paths = ("docs/agent-system/HANDOFF.md", "docs/agent-system/TASKS.md", request.exec_plan_path)
        if tuple(paths) != canonical_paths or not request.exec_plan_path.startswith("docs/exec-plans/active/") or not request.exec_plan_path.endswith(".md"):
            raise ValueError("ops sync requires exact canonical HANDOFF, TASKS and active ExecPlan updates")
        return tuple(paths)

    def _run(self, argv: tuple[str, ...], cwd: Path):
        result = self.runner(argv, cwd)
        if result.returncode != 0:
            raise ValueError(f"ops sync command failed: {' '.join(argv[:3])}")
        return result

    def sync(self, request: OpsSyncInput) -> OpsSyncReadback:
        paths = self._validate(request)
        request_digest = _request_digest(request)
        if self.approval_authority is None:
            raise ValueError("ops sync approval authority is unavailable")
        approval = self.approval_authority(request.approval_id)
        if (approval.approval_id, approval.request_digest, approval.approver) != (request.approval_id, request_digest, "Mike") or request.approval_digest != request_digest or not approval.source_ref:
            raise ValueError("ops sync approval readback mismatch")
        root = request.repo_root.resolve()
        if not root.is_dir():
            raise ValueError("ops sync repository root is absent")
        top = self._run(("git", "rev-parse", "--show-toplevel"), root).stdout.strip()
        if Path(top).resolve() != root:
            raise ValueError("ops sync repository root readback mismatch")
        common = self._run(("git", "rev-parse", "--path-format=absolute", "--git-common-dir"), root).stdout.strip()
        repo_result = self._run(("gh", "repo", "view", "--json", "nameWithOwner"), root)
        try:
            repo_data = json.loads(repo_result.stdout)
        except json.JSONDecodeError as error:
            raise ValueError("ops sync repository authority readback is malformed") from error
        if not isinstance(repo_data, dict) or set(repo_data) != {"nameWithOwner"} or repo_data.get("nameWithOwner") != request.repo:
            raise ValueError("ops sync repository authority readback mismatch")
        journal = ProvenanceJournal(Path(common), request_digest)
        with journal.locked():
            events = journal.events()
            worktree_events = [event for event in events if event.get("event") == "ops_step_intent" and event.get("step") == "worktree"]
            if len(worktree_events) > 1 or (worktree_events and not isinstance(worktree_events[0].get("worktree"), str)):
                raise ValueError("ops worktree WAL identity is malformed")
            worktree = Path(worktree_events[0]["worktree"]).absolute() if worktree_events else self.path_factory(request_digest).absolute()
            completed = {event.get("step") for event in events if event.get("event") == "ops_step_done"}
            pending = {
                event.get("step")
                for event in events
                if event.get("event") == "ops_step_intent"
            } - completed
            if "worktree" not in completed:
                if "worktree" in pending:
                    if worktree.is_symlink() or not worktree.is_dir():
                        raise ValueError("pending ops worktree cannot be reconciled")
                    reconciled_top = self._run(("git", "rev-parse", "--show-toplevel"), worktree).stdout.strip()
                    if Path(reconciled_top).resolve() != worktree.resolve():
                        raise ValueError("pending ops worktree identity mismatch")
                else:
                    if worktree.exists() or worktree.is_symlink():
                        raise ValueError("isolated ops worktree target already exists without receipt")
                    journal.append("ops_step_intent", step="worktree", worktree=str(worktree), base_ref=request.base_ref)
                    self._run(("git", "worktree", "add", "--detach", str(worktree), request.base_ref), root)
                journal.append("ops_step_done", step="worktree")
            elif not worktree.is_dir() or worktree.is_symlink():
                raise ValueError("ops worktree receipt cannot be reconciled")
            if "branch" not in completed:
                if "branch" in pending:
                    current = self._run(("git", "branch", "--show-current"), worktree).stdout.strip()
                    if current != request.branch:
                        self._run(("git", "switch", "-c", request.branch), worktree)
                else:
                    journal.append("ops_step_intent", step="branch", branch=request.branch)
                    self._run(("git", "switch", "-c", request.branch), worktree)
                current = self._run(("git", "branch", "--show-current"), worktree).stdout.strip()
                if current != request.branch:
                    raise ValueError("ops branch readback mismatch")
                journal.append("ops_step_done", step="branch", branch=request.branch)
            for update in request.updates:
                step = f"write:{update.path}"
                if step not in completed:
                    if step in pending:
                        if _safe_read(worktree, update.path) != update.content:
                            raise ValueError("pending ops write cannot be reconciled without duplicate write")
                    else:
                        journal.append("ops_step_intent", step=step, content_digest=sha256(update.content.encode()).hexdigest())
                        _safe_write(worktree, update.path, update.content)
                    journal.append("ops_step_done", step=step)
            if "stage" not in completed:
                if "stage" in pending:
                    staged = self._run(("git", "diff", "--cached", "--name-only"), worktree).stdout.splitlines()
                else:
                    journal.append("ops_step_intent", step="stage", paths=list(paths))
                    self._run(("git", "add", "--", *paths), worktree)
                    staged = self._run(("git", "diff", "--cached", "--name-only"), worktree).stdout.splitlines()
                if tuple(staged) != paths:
                    raise ValueError("staged paths do not exactly match owned updates or pending stage receipt")
                journal.append("ops_step_done", step="stage")
            if "commit" not in completed:
                if "commit" in pending:
                    clean_index = self.runner(("git", "diff", "--cached", "--quiet"), worktree)
                    if clean_index.returncode != 0:
                        raise ValueError("pending ops commit cannot be reconciled without duplicate commit")
                else:
                    journal.append("ops_step_intent", step="commit")
                    self._run(("git", "commit", "-m", request.commit_message), worktree)
                journal.append("ops_step_done", step="commit")
            head = self._run(("git", "rev-parse", "HEAD"), worktree).stdout.strip()
            if not _HEAD.fullmatch(head):
                raise ValueError("ops sync HEAD readback is invalid")
            if "push" not in completed:
                if "push" in pending:
                    remote = self._run(("git", "ls-remote", "--heads", "origin", request.branch), worktree).stdout.split()
                    if not remote or remote[0] != head:
                        raise ValueError("pending ops push cannot be reconciled without duplicate push")
                else:
                    journal.append("ops_step_intent", step="push", head=head)
                    self._run(("git", "push", "-u", "origin", request.branch), worktree)
                journal.append("ops_step_done", step="push", head=head)
            base = request.base_ref.removeprefix("origin/")
            blob_values = []
            for path in paths:
                blob = self._run(("git", "rev-parse", f"{head}:{path}"), worktree).stdout.strip()
                if not _HEAD.fullmatch(blob):
                    raise ValueError("ops sync canonical blob readback is invalid")
                blob_values.append(blob)
            existing = self.runner(("gh", "pr", "view", request.branch, "--json", "number,state,baseRefName,headRefName,headRefOid,url"), worktree)
            if existing.returncode != 0:
                absence = self.runner(("gh", "pr", "list", "--head", request.branch, "--base", base, "--state", "open", "--json", "number,state,baseRefName,headRefName,headRefOid,url"), worktree)
                try:
                    absence_rows = json.loads(absence.stdout)
                except json.JSONDecodeError as error:
                    raise ValueError("ops sync PR absence readback is malformed") from error
                if absence.returncode != 0 or not isinstance(absence_rows, list) or absence_rows:
                    raise ValueError("ops sync PR lookup is not a proven absence")
                journal.append("ops_step_intent", step="pr", head=head)
                self._run(("gh", "pr", "create", "--head", request.branch, "--base", base, "--title", request.pr_title, "--body", request.pr_body), worktree)
                journal.append("ops_step_done", step="pr", head=head)
            readback = self._run(("gh", "pr", "view", request.branch, "--json", "number,state,baseRefName,headRefName,headRefOid,url"), worktree)
        try:
            data = json.loads(readback.stdout)
        except json.JSONDecodeError as error:
            raise ValueError("ops sync PR readback is malformed") from error
        if not isinstance(data, dict) or type(data.get("number")) is not int or data["number"] <= 0 or data.get("state") != "OPEN" or data.get("baseRefName") != base or data.get("headRefName") != request.branch or data.get("headRefOid") != head or not isinstance(data.get("url"), str):
            raise ValueError("ops sync PR readback is mismatched")
        return OpsSyncReadback(str(worktree), request.branch, head, data["number"], data["state"], data["url"], request_digest, request_digest, None, request.repo, base, request.task_key, request.dispatch_id, request.issue_key, request.scope_digest, request.product_merge_commit, blob_values[0], blob_values[1], request.exec_plan_path, blob_values[2])
