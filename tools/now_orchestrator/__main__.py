from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import load_snapshot, render, select
from .core.snapshot import first_run_snapshot
from .jira import ExecutionContract, JiraIntent, JiraLedger, JiraReconciliation, JiraResult


def _read_json(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("JSON input must be an object")
    return raw


def _intent(data: dict[str, object]) -> JiraIntent:
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("intent payload must be an object")
    actor, operation, project = (data.get(field) for field in ("actor", "operation", "project"))
    issue_key = data.get("issue_key")
    if not all(isinstance(field, str) for field in (actor, operation, project)) or not (issue_key is None or isinstance(issue_key, str)):
        raise ValueError("intent identity fields are invalid")
    raw_contract = data.get("execution_contract")
    contract = None
    if raw_contract is not None:
        if not isinstance(raw_contract, dict):
            raise ValueError("execution contract must be an object")
        fields = ("owner", "owner_account_id", "lane", "blockers", "acceptance_criteria", "definition_of_done", "gate_id", "evidence_locators", "zones")
        if not all(field in raw_contract for field in fields):
            raise ValueError("execution contract fields are incomplete")
        try:
            contract = ExecutionContract(
                raw_contract["owner"], raw_contract["owner_account_id"], raw_contract["lane"], tuple(raw_contract["blockers"]), tuple(raw_contract["acceptance_criteria"]), tuple(raw_contract["definition_of_done"]), raw_contract["gate_id"], tuple(raw_contract["evidence_locators"]), tuple(raw_contract["zones"])
            )
        except TypeError as error:
            raise ValueError("execution contract fields are invalid") from error
    optional = {field: data[field] for field in ("issue_count", "assignee", "assignee_account_id", "replaces_scope") if field in data}
    return JiraIntent(actor, operation, project, issue_key, payload, contract, **optional)  # type: ignore[arg-type]


def _result(data: dict[str, object]) -> JiraResult:
    intent_id, success = data.get("intent_id"), data.get("success")
    remote_evidence_id = data.get("remote_evidence_id")
    if not isinstance(intent_id, str) or type(success) is not bool or not (remote_evidence_id is None or isinstance(remote_evidence_id, str)):
        raise ValueError("result fields are invalid")
    return JiraResult(intent_id, success, remote_evidence_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a deterministic read-only /now snapshot", allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="command")
    render_parser = subparsers.add_parser("render", help="render a normalized snapshot JSON")
    render_parser.add_argument("snapshot", type=Path, nargs="?", help="path to normalized snapshot JSON")
    render_parser.add_argument("--stdin", action="store_true", help="read normalized snapshot JSON from stdin")
    jira_parser = subparsers.add_parser("jira", help="authorize or record a non-network Jira audit event")
    jira_subparsers = jira_parser.add_subparsers(dest="jira_command", required=True)
    authorize_parser = jira_subparsers.add_parser("authorize", help="classify and append a Jira intent before a client MCP write")
    authorize_parser.add_argument("--intent", type=Path, required=True, help="path to intent JSON")
    record_parser = jira_subparsers.add_parser("record", help="append a Jira MCP outcome for an authorized intent")
    record_parser.add_argument("--result", type=Path, required=True, help="path to outcome JSON")
    reconcile_parser = jira_subparsers.add_parser("reconcile", help="append evidence-backed Jira read reconciliation after a failed outcome")
    reconcile_parser.add_argument("--result", type=Path, required=True, help="path to reconciliation JSON")
    args = parser.parse_args()
    if args.command is None:
        print(render(select(first_run_snapshot())), end="")
        return 0
    if args.command == "render":
        try:
            if args.stdin == (args.snapshot is not None):
                parser.error("provide exactly one snapshot path or --stdin")
            raw = sys.stdin.read() if args.stdin else args.snapshot.read_text(encoding="utf-8")
            data = json.loads(raw)
            print(render(select(load_snapshot(data))), end="")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            parser.error(str(error))
    if args.command == "jira":
        try:
            ledger = JiraLedger()
            if args.jira_command == "authorize":
                intent = _intent(_read_json(args.intent))
                decision, intent_id = ledger.authorize(intent)
                print(json.dumps({"intent_id": intent_id, "status": decision.status, "reason": decision.reason, "payload_digest": decision.payload_digest}, sort_keys=True))
            if args.jira_command == "record":
                ledger.record(_result(_read_json(args.result)))
                print('{"recorded": true}')
            if args.jira_command == "reconcile":
                data = _read_json(args.result)
                intent_id, evidence_id, effect_present = data.get("intent_id"), data.get("remote_evidence_id"), data.get("effect_present")
                if not isinstance(intent_id, str) or not isinstance(evidence_id, str) or type(effect_present) is not bool:
                    raise ValueError("reconciliation fields are invalid")
                ledger.reconcile(JiraReconciliation(intent_id, evidence_id, effect_present))
                print('{"reconciled": true}')
        except (OSError, ValueError, json.JSONDecodeError) as error:
            parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
