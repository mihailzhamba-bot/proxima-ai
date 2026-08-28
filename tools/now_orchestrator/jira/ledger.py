from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
from hashlib import sha256

from .policy import JiraDecision, JiraIntent, JiraReadback, JiraReconciliation, JiraResult, authorize


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
            offset = 0
            while offset < len(payload):
                written = os.write(fd, payload[offset:])
                if written <= 0:
                    raise OSError("short Jira ledger write")
                offset += written
            os.fsync(fd)
        finally:
            os.close(fd)
        directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def authorize(self, intent: JiraIntent) -> tuple[JiraDecision, str]:
        """Compute the decision internally, bind its digest and append the pre-write event."""
        decision = authorize(intent)
        intent_id = sha256(
            "\0".join(
                (
                    intent.actor,
                    intent.operation,
                    intent.project,
                    intent.issue_key or "",
                    decision.payload_digest,
                )
            ).encode()
        ).hexdigest()
        existing = [event for event in self._events() if event.get("event") == "intent" and event.get("intent_id") == intent_id]
        if existing:
            event = existing[0]
            if len(existing) != 1 or (event.get("actor"), event.get("operation"), event.get("project"), event.get("issue_key"), event.get("decision"), event.get("payload_digest")) != (intent.actor, intent.operation, intent.project, intent.issue_key, decision.status, decision.payload_digest):
                raise ValueError("Jira intent receipt collision")
            return decision, intent_id
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

    def events_for(self, intent_id: str) -> tuple[dict[str, object], ...]:
        _, events = self._intent_and_events(intent_id)
        return tuple(events)

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
            outcome_index = events.index(last_outcome)
            reconciliations = [event for event in events[outcome_index + 1:] if event.get("event") == "reconciliation"]
            if last_outcome.get("success") is not False or len(reconciliations) != 1:
                raise ValueError("retry requires a failed outcome followed by reconciliation")
            if reconciliations[0].get("effect_present") is not False:
                raise ValueError("retry is denied after a reconciled remote effect")
        self._append(
            {
                "event": "outcome",
                "intent_id": result.intent_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "success": result.success,
                "remote_evidence_id": result.remote_evidence_id,
            }
        )

    def record_write_intent(self, intent_id: str) -> tuple[int, bool]:
        _, events = self._intent_and_events(intent_id)
        started = [event for event in events if event.get("event") == "write_intent"]
        outcomes = [event for event in events if event.get("event") == "outcome"]
        if any(type(event.get("attempt")) is not int or event.get("attempt", 0) < 1 for event in started) or len(started) > len(outcomes) + 1:
            raise ValueError("Jira write intent receipt sequence is invalid")
        if len(started) == len(outcomes) + 1:
            return len(started), True
        if outcomes and (events[-1].get("event") != "reconciliation" or events[-1].get("effect_present") is not False):
            raise ValueError("Jira write intent follows an unresolved outcome")
        attempt = len(outcomes) + 1
        self._append({"event": "write_intent", "intent_id": intent_id, "attempt": attempt, "timestamp": datetime.now(UTC).isoformat()})
        return attempt, False

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

    def confirm_remote_effect(self, intent_id: str, remote_evidence_id: str) -> None:
        _, events = self._intent_and_events(intent_id)
        if not remote_evidence_id:
            raise ValueError("remote effect confirmation requires evidence ID")
        outcomes = [event for event in events if event.get("event") == "outcome"]
        if not outcomes or outcomes[-1].get("success") is not False:
            raise ValueError("remote effect confirmation requires a failed outcome")
        self._append({"event": "remote_effect_confirmed", "intent_id": intent_id, "timestamp": datetime.now(UTC).isoformat(), "remote_evidence_id": remote_evidence_id})

    def record_readback(self, readback: JiraReadback) -> None:
        _, events = self._intent_and_events(readback.intent_id)
        outcomes = [event for event in events if event.get("event") == "outcome"]
        reconciled_present = bool(events and events[-1].get("event") == "remote_effect_confirmed")
        if not outcomes or (outcomes[-1].get("success") is not True and not reconciled_present):
            raise ValueError("remote readback requires a successful outcome")
        if any(event.get("event") == "readback" for event in events):
            raise ValueError("remote readback is immutable")
        if not all(isinstance(value, str) and value for value in (readback.issue_key, readback.status, readback.remote_evidence_id)):
            raise ValueError("remote readback identity is invalid")
        self._append({"event": "readback", "intent_id": readback.intent_id, "timestamp": datetime.now(UTC).isoformat(), "issue_key": readback.issue_key, "status": readback.status, "remote_evidence_id": readback.remote_evidence_id})
