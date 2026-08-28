from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .core import load_snapshot, render, select
from .core.snapshot import first_run_snapshot
from .facades import FACADE_ENTRIES
from .jira import ExecutionContract, JiraIntent, JiraLedger, JiraReconciliation, JiraResult
from .runtime import ClaimStore, GoCommand, advance
from .runtime import ActionPlan, ClaimRequest, LifecycleState
from .integration import CloseCoordinator, CloseInput, DispatchInput, DispatchProvenance, IntegrationCoordinator, MergeApprovalEvidence, MirrorRequirement, OpsSyncReadback, ReviewEvidence, WorktreePlacement


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


def _common_dir() -> Path:
    completed = subprocess.run(["git", "rev-parse", "--git-common-dir"], check=True, text=True, capture_output=True)
    return Path(completed.stdout.strip()).resolve()


def _repo_root() -> Path:
    completed = subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True, text=True, capture_output=True)
    return Path(completed.stdout.strip()).resolve()


def _plan(data: dict[str, object]) -> ActionPlan:
    required = {"key", "track", "state", "run_id", "task_id", "worker_id", "claim_token", "dispatch", "should_dispatch", "blocked", "reason"}
    if set(data) - required or not required.issubset(data):
        raise ValueError("plan fields are incomplete or unexpected")
    state = data["state"]
    if not isinstance(state, str) or not all(data[name] is None or isinstance(data[name], str) for name in ("key", "track", "run_id", "task_id", "worker_id", "claim_token", "reason")) or not all(type(data[name]) is bool for name in ("dispatch", "should_dispatch", "blocked")):
        raise ValueError("plan state is invalid")
    try:
        return ActionPlan(data["key"], data["track"], LifecycleState(state), data["run_id"], data["task_id"], data["worker_id"], data["claim_token"], data["dispatch"], data["should_dispatch"], data["blocked"], data["reason"])  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError("plan fields are invalid") from error


def _exact(data: object, fields: set[str], label: str) -> dict[str, object]:
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError(f"{label} fields are missing or unexpected")
    return data


def _strings(data: dict[str, object], names: tuple[str, ...], label: str) -> None:
    if not all(isinstance(data[name], str) and data[name] for name in names):
        raise ValueError(f"{label} string fields are invalid")


def _close_request(raw: dict[str, object], repo_root: Path) -> CloseInput:
    top = {"plan", "dispatch", "review", "approval", "expected_repo", "expected_base_ref", "expected_mike_identity", "issue_key", "expected_jira_status", "expected_jira_transition", "expected_jira_payload_digest", "mirrors", "ops_sync"}
    _exact(raw, top, "close envelope")
    plan = _plan(_exact(raw["plan"], {"key", "track", "state", "run_id", "task_id", "worker_id", "claim_token", "dispatch", "should_dispatch", "blocked", "reason"}, "close plan"))
    dispatch_raw = _exact(raw["dispatch"], set(DispatchProvenance.__dataclass_fields__), "dispatch receipt")
    _strings(dispatch_raw, tuple(dispatch_raw), "dispatch receipt")
    review_raw = _exact(raw["review"], set(ReviewEvidence.__dataclass_fields__), "review receipt")
    _strings(review_raw, tuple(name for name in review_raw if name not in {"blockers", "warnings", "verify_exit_code", "verify_output_ref"}), "review receipt")
    if type(review_raw["blockers"]) is not int or type(review_raw["warnings"]) is not int or type(review_raw["verify_exit_code"]) is not int:
        raise ValueError("review counters are invalid")
    approval_raw = _exact(raw["approval"], set(MergeApprovalEvidence.__dataclass_fields__), "approval receipt")
    _strings(approval_raw, tuple(name for name in approval_raw if name != "pr_number"), "approval receipt")
    if type(approval_raw["pr_number"]) is not int or approval_raw["pr_number"] <= 0:
        raise ValueError("approval PR number is invalid")
    ops_raw = _exact(raw["ops_sync"], set(OpsSyncReadback.__dataclass_fields__), "ops sync receipt")
    _strings(ops_raw, tuple(name for name in ops_raw if name not in {"pr_number", "merge_commit"}), "ops sync receipt")
    if type(ops_raw["pr_number"]) is not int or not (ops_raw["merge_commit"] is None or isinstance(ops_raw["merge_commit"], str)):
        raise ValueError("ops sync receipt types are invalid")
    mirrors_raw = raw["mirrors"]
    if not isinstance(mirrors_raw, list):
        raise ValueError("mirrors must be a list")
    mirrors: list[MirrorRequirement] = []
    for item in mirrors_raw:
        parsed = _exact(item, {"path", "required_tokens"}, "mirror")
        tokens = parsed["required_tokens"]
        if not isinstance(parsed["path"], str) or not isinstance(tokens, list) or not tokens or not all(isinstance(token, str) and token for token in tokens):
            raise ValueError("mirror fields are invalid")
        mirrors.append(MirrorRequirement(parsed["path"], tuple(tokens)))
    scalar_names = ("expected_repo", "expected_base_ref", "expected_mike_identity", "issue_key", "expected_jira_status", "expected_jira_transition", "expected_jira_payload_digest")
    _strings(raw, scalar_names, "close envelope")
    return CloseInput(plan, DispatchProvenance(**dispatch_raw), ReviewEvidence(**review_raw), MergeApprovalEvidence(**approval_raw), repo_root, *(raw[name] for name in scalar_names), tuple(mirrors), OpsSyncReadback(**ops_raw))  # type: ignore[arg-type]


def _snapshot_argument(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("snapshot", type=Path, nargs="?", help="path to fresh normalized snapshot JSON")
    command_parser.add_argument("--stdin", action="store_true", help="read fresh normalized snapshot JSON from stdin")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a deterministic read-only /now snapshot", allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="command")
    render_parser = subparsers.add_parser("render", help="render a normalized snapshot JSON")
    _snapshot_argument(render_parser)
    facade_parser = subparsers.add_parser("facade", help="run one real client facade entry")
    facade_parser.add_argument("client", choices=tuple(FACADE_ENTRIES))
    _snapshot_argument(facade_parser)
    go_parser = subparsers.add_parser("go", help="validate a fresh selected key and return a non-dispatching ActionPlan")
    go_parser.add_argument("key", help="exact fresh selected Jira key")
    go_parser.add_argument("--owner", default="Mike", help="claim owner token")
    _snapshot_argument(go_parser)
    jira_parser = subparsers.add_parser("jira", help="authorize or record a non-network Jira audit event")
    jira_subparsers = jira_parser.add_subparsers(dest="jira_command", required=True)
    authorize_parser = jira_subparsers.add_parser("authorize", help="classify and append a Jira intent before a client MCP write")
    authorize_parser.add_argument("--intent", type=Path, required=True, help="path to intent JSON")
    record_parser = jira_subparsers.add_parser("record", help="append a Jira MCP outcome for an authorized intent")
    record_parser.add_argument("--result", type=Path, required=True, help="path to outcome JSON")
    reconcile_parser = jira_subparsers.add_parser("reconcile", help="append evidence-backed Jira read reconciliation after a failed outcome")
    reconcile_parser.add_argument("--result", type=Path, required=True, help="path to reconciliation JSON")
    dispatch_parser = subparsers.add_parser("dispatch", help="execute only a confirmed, proven Orca dispatch")
    dispatch_parser.add_argument("--plan", type=Path, required=True)
    dispatch_parser.add_argument("--gate", type=Path, required=True)
    close_parser = subparsers.add_parser("close", help="validate typed close evidence and perform live readbacks")
    close_parser.add_argument("--evidence", type=Path, required=True)
    close_parser.add_argument("--client", choices=("codex", "claude", "opencode"), default="codex")
    args = parser.parse_args()
    if args.command is None:
        print(render(select(first_run_snapshot())), end="")
        return 0
    if args.command in {"render", "facade"}:
        try:
            if args.stdin == (args.snapshot is not None):
                parser.error("provide exactly one snapshot path or --stdin")
            raw = sys.stdin.read() if args.stdin else args.snapshot.read_text(encoding="utf-8")
            data = json.loads(raw)
            snapshot = load_snapshot(data)
            print(render(select(snapshot)) if args.command == "render" else FACADE_ENTRIES[args.client](snapshot), end="")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            parser.error(str(error))
    if args.command == "go":
        try:
            if args.stdin == (args.snapshot is not None):
                parser.error("provide exactly one snapshot path or --stdin")
            raw = sys.stdin.read() if args.stdin else args.snapshot.read_text(encoding="utf-8")
            plan = advance(GoCommand(args.key, args.owner), load_snapshot(json.loads(raw)), ClaimStore(_common_dir()))
            print(json.dumps(plan.as_dict(), sort_keys=True, separators=(",", ":")))
        except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
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
    if args.command == "dispatch":
        try:
            raw_plan = _read_json(args.plan)
            expected_dispatch_fields = {"plan", "gate_id", "spec", "task_title", "display_name", "coordinator_handle", "worktree"}
            _exact(raw_plan, expected_dispatch_fields, "dispatch envelope")
            raw_action = raw_plan.get("plan")
            if not isinstance(raw_action, dict): raise ValueError("dispatch plan envelope is invalid")
            plan = _plan(raw_action)
            required = ("spec", "task_title", "display_name", "coordinator_handle", "worktree")
            gate_id = raw_plan.get("gate_id")
            if not isinstance(gate_id, str) or not all(isinstance(raw_plan.get(field), str) for field in required): raise ValueError("dispatch fields are invalid")
            root = _repo_root()
            common = _common_dir()
            placement = WorktreePlacement(plan.key or "", plan.claim_token or "", str(root), str(common.resolve()), "current", f"git:{root}")
            next_plan, provenance = IntegrationCoordinator(ClaimStore(common), root, placement_authority=lambda _: placement).dispatch(DispatchInput(plan, gate_id, args.gate, *(raw_plan[field] for field in required)))  # type: ignore[arg-type]
            print(json.dumps({"plan": next_plan.as_dict(), "provenance": None if provenance is None else provenance.__dict__}, sort_keys=True))
        except (OSError, TypeError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
            parser.error(str(error))
    if args.command == "close":
        try:
            request = _close_request(_read_json(args.evidence), _repo_root())
            result, evidence = CloseCoordinator(None, None, None, None).close(request)
            side_effect_plan = None if args.client == "codex" else {
                "protocol": "now.close.v1",
                "executable": False,
                "execution_owner": f"{args.client}:approved-tool-adapter",
                "resume": "readback-first",
                "requires": ["dispatch_receipt_read", "review_receipt_read", "mike_decision_gate_read", "ops_sync_receipt_read", "gh_pr_read", "jira_transition_and_readback", "orca_settlement_and_release_readback"],
                "receipt_binding": ["task_key", "claim_token", "gate_binding_digest", "dispatch_id", "worker_id", "issue_key", "repo", "base_ref", "reviewed_head", "scope_digest", "operation_id"],
            }
            print(json.dumps({"plan": result.as_dict(), "evidence": None, "side_effect_plan": side_effect_plan}, sort_keys=True))
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
            parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
