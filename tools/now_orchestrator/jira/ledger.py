from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

from .policy import JiraDecision, JiraIntent, JiraReconciliation, JiraResult, authorize


def git_common_dir() -> Path:
    common_dir = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return Path(common_dir)


def ledger_path(common_dir: Path | None = None) -> Path:
    """Return the sole permitted append-only ledger location below Git common-dir."""
    return (common_dir or git_common_dir()) / "now" / "evidence" / "jira-ledger.jsonl"


class JiraLedger:
    """Append-only evidence ledger; test paths must remain inside a supplied common-dir."""
    def __init__(self, path: Path | None = None, *, common_dir: Path | None = None) -> None:
        self.common_dir = (common_dir or git_common_dir()).absolute()
        self.path = path or ledger_path(self.common_dir)
        self._validate_path()

    def _validate_path(self) -> None:
        base = self.common_dir
        allowed_root = base / "now" / "evidence"
        candidate = self.path.absolute()
        if base.is_symlink():
            raise ValueError("Git common-dir must not be a symlink")
        probe = base
        try:
            parts = candidate.relative_to(base).parts
        except ValueError:
            parts = ()
        for part in parts:
            probe = probe / part
            if probe.exists() and probe.is_symlink():
                raise ValueError("ledger path must not follow a symlink")
        try:
            candidate.relative_to(allowed_root)
        except ValueError as error:
            raise ValueError("ledger path must remain in Git common-dir evidence area") from error
        resolved_base = base.resolve(strict=False)
        resolved_candidate = candidate.resolve(strict=False)
        try:
            resolved_candidate.relative_to(resolved_base / "now" / "evidence")
        except ValueError as error:
            raise ValueError("ledger path escapes Git common-dir evidence area") from error

    def _append(self, event: dict[str, object]) -> None:
        self._validate_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._validate_path()
        payload = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)

    def authorize(self, intent: JiraIntent) -> tuple[JiraDecision, str]:
        """Compute the decision internally, bind its digest and append the pre-write event."""
        decision = authorize(intent)
        intent_id = uuid4().hex
        self._append(
            {
                "event": "intent",
                "intent_id": intent_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "actor": intent.actor,
                "operation": intent.operation,
                "project": intent.project,
                "issue_key": intent.issue_key,
                "decision": decision.status,
                "reason": decision.reason,
                "payload_digest": decision.payload_digest,
            }
        )
        return decision, intent_id

    def _events(self) -> list[dict[str, object]]:
        self._validate_path()
        if not self.path.exists():
            return []
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            raw = os.read(fd, os.fstat(fd).st_size).decode("utf-8")
        finally:
            os.close(fd)
        return [json.loads(line) for line in raw.splitlines() if line]

    def _intent_and_events(self, intent_id: str) -> tuple[dict[str, object], list[dict[str, object]]]:
        events = self._events()
        intent = next((event for event in events if event.get("event") == "intent" and event.get("intent_id") == intent_id), None)
        if intent is None or intent.get("decision") != "AUTO":
            raise ValueError("outcome requires an existing authorized intent")
        return intent, [event for event in events if event.get("intent_id") == intent_id]

    def record(self, result: JiraResult) -> None:
        _, events = self._intent_and_events(result.intent_id)
        if result.success and not result.remote_evidence_id:
            raise ValueError("successful outcome requires remote evidence ID")
        outcomes = [event for event in events if event.get("event") == "outcome"]
        if outcomes:
            last_outcome = outcomes[-1]
            if last_outcome.get("success") is not False or not events or events[-1].get("event") != "reconciliation":
                raise ValueError("retry requires a failed outcome followed by reconciliation")
        self._append(
            {
                "event": "outcome",
                "intent_id": result.intent_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "success": result.success,
                "remote_evidence_id": result.remote_evidence_id,
            }
        )

    def reconcile(self, reconciliation: JiraReconciliation) -> None:
        _, events = self._intent_and_events(reconciliation.intent_id)
        if not reconciliation.remote_evidence_id:
            raise ValueError("reconciliation requires remote evidence ID")
        if reconciliation.effect_present is not False:
            raise ValueError("reconciliation found an existing remote effect; retry is denied")
        outcomes = [event for event in events if event.get("event") == "outcome"]
        if not outcomes or outcomes[-1].get("success") is not False:
            raise ValueError("reconciliation requires a failed outcome")
        self._append(
            {
                "event": "reconciliation",
                "intent_id": reconciliation.intent_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "remote_evidence_id": reconciliation.remote_evidence_id,
                "effect_present": reconciliation.effect_present,
            }
        )
