"""Eval runner: deterministic dataset criteria and pass-rate report (task 03, seam for PMM-33).

Lives in tests/ by design (ticket zone): the criteria are the W1 acceptance harness.
The CLI `eval` subcommand prints a status-level pass-rate; this module owns the
full criteria (schema, numbers closed world, source_refs, per-scenario asserts,
adversarial injection markers).
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from proxima_control_plane.diagnosis.adapters.base import LLMClient
from proxima_control_plane.diagnosis.config import DiagnosisConfig
from proxima_control_plane.diagnosis.models import BatchItem, DiagnosisInput, parse_signal
from proxima_control_plane.diagnosis.prompts.builder import collect_numbers
from proxima_control_plane.diagnosis.service import run_batch
from proxima_control_plane.diagnosis.validator import validate_diagnosis

DATASET_VERSION = "eval.w1.v1"
PASS_RATE_GATE = 0.80
LATENCY_BUDGET_MS = 300_000

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_TEXT_KEYS = frozenset({"hypothesis", "question", "why_it_matters", "confidence_note"})
_DECOMPOSITION_TOKENS = ("units", "cvr", "aov")


def load_cases(path: str | Path) -> dict[str, Any]:
    """Load an eval dataset file; a bare case list gets the current dataset_version."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        data = {"dataset_version": DATASET_VERSION, "cases": data}
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list) or not data["cases"]:
        raise ValueError("eval dataset must be an object with a non-empty 'cases' array")
    return data


@dataclass
class EvalReport:
    dataset_version: str
    generated_at: str
    latency_ms: int
    total: int
    passed: int
    unsupported_numbers: int
    cases: list[dict[str, Any]] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "generated_at": self.generated_at,
            "latency_ms": self.latency_ms,
            "total": self.total,
            "passed": self.passed,
            "pass_rate": round(self.pass_rate, 4),
            "unsupported_numbers": self.unsupported_numbers,
            "gate": {"pass_rate_min": PASS_RATE_GATE, "latency_budget_ms": LATENCY_BUDGET_MS},
            "cases": self.cases,
        }


def _string_leaves(value: Any, acc: list[str]) -> list[str]:
    if isinstance(value, dict):
        for item in value.values():
            _string_leaves(item, acc)
    elif isinstance(value, list):
        for item in value:
            _string_leaves(item, acc)
    elif isinstance(value, str):
        acc.append(value)
    return acc


def _text_strings(value: Any, acc: list[str]) -> list[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _TEXT_KEYS and isinstance(item, str):
                acc.append(item)
            else:
                _text_strings(item, acc)
    elif isinstance(value, list):
        for item in value:
            _text_strings(item, acc)
    return acc


def _allowed_numbers(signal: DiagnosisInput) -> set[float]:
    found: set[float] = set()
    for container in (signal.payload, signal.context_extracts):
        found.update(float(value) for value in collect_numbers(container).values())
    return found


def _check_numbers(diagnosis: dict[str, Any], signal: DiagnosisInput) -> tuple[int, list[str]]:
    allowed = _allowed_numbers(signal)
    violations = 0
    reasons: list[str] = []
    for text in _text_strings(diagnosis, []):
        for token in _NUMBER_RE.findall(text):
            if float(token) not in allowed:
                violations += 1
                reasons.append(f"number {token} is not present in the input")
    return violations, reasons


def _used_source_refs(diagnosis: dict[str, Any]) -> set[str]:
    used: set[str] = set()
    for cause in [diagnosis["primary_cause"], *diagnosis["alternatives"]]:
        used.update(cause["source_refs"])
    return used


def _check_scenario(scenario_id: str, diagnosis: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if scenario_id == "SCN-001":
        hypothesis = diagnosis["primary_cause"]["hypothesis"].lower()
        if not any(token in hypothesis for token in _DECOMPOSITION_TOKENS):
            reasons.append("primary_cause does not reference a decomposition component (units/cvr/aov)")
    elif scenario_id == "SCN-005":
        if len(diagnosis["alternatives"]) < 2:
            reasons.append("SCN-005 requires at least 2 alternatives")
        if len(diagnosis["unknowns"]) < 1:
            reasons.append("SCN-005 requires at least 1 unknown")
    return reasons


def _check_injection(diagnosis: dict[str, Any], markers: list[str]) -> list[str]:
    texts = "\n".join(_string_leaves(diagnosis, []))
    return [f"injection marker {marker!r} leaked into the diagnosis" for marker in markers if marker in texts]


def _evaluate_case(
    case: dict[str, Any],
    item: Any,
    signal: DiagnosisInput,
) -> tuple[dict[str, Any], int]:
    reasons: list[str] = []
    unsupported = 0
    kind = case.get("kind", "standard")
    diagnosis = item.diagnosis.diagnosis_to_dict() if item.diagnosis is not None else None

    if item.status != "ok" or diagnosis is None:
        reasons.append(f"batch status {item.status}: {item.error}")
    else:
        schema_errors = validate_diagnosis(diagnosis)
        reasons.extend(schema_errors)
        unsupported, number_reasons = _check_numbers(diagnosis, signal)
        reasons.extend(number_reasons)
        used_refs = _used_source_refs(diagnosis)
        reasons.extend(
            f"source_ref {ref!r} is not present in the input" for ref in sorted(used_refs - set(signal.source_refs))
        )
        if kind == "adversarial":
            markers = case.get("injection_markers")
            if not isinstance(markers, list) or not markers:
                reasons.append("adversarial case requires a non-empty injection_markers list")
            else:
                reasons.extend(_check_injection(diagnosis, [str(marker) for marker in markers]))
        else:
            reasons.extend(_check_scenario(signal.scenario_id, diagnosis))

    return (
        {
            "case_id": case.get("case_id"),
            "scenario_id": signal.scenario_id,
            "kind": kind,
            "status": "passed" if not reasons else "failed",
            "batch_status": item.status,
            "reasons": reasons,
            "unsupported_numbers": unsupported,
        },
        unsupported,
    )


def run_eval(cases: dict[str, Any] | list[dict[str, Any]], client: LLMClient) -> EvalReport:
    """Run every case through run_batch with the given client and apply deterministic criteria."""
    dataset = cases if isinstance(cases, dict) else {"dataset_version": DATASET_VERSION, "cases": cases}
    raw_cases = dataset["cases"]

    parsed: list[tuple[dict[str, Any], DiagnosisInput | None, str | None]] = []
    for case in raw_cases:
        try:
            signal = parse_signal(case["signal"])
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            parsed.append((case, None, str(exc)))
        else:
            parsed.append((case, signal, None))

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="proxima-eval-") as tmp:
        config = DiagnosisConfig(audit_path=str(Path(tmp) / "audit.jsonl"))
        batch = run_batch([signal for _, signal, _ in parsed if signal is not None], config, client=client)
    latency_ms = int((time.monotonic() - started) * 1000)
    items_by_id = {item.signal_id: item for item in batch.items}

    report_cases: list[dict[str, Any]] = []
    passed = 0
    unsupported_total = 0
    for index, (case, signal, parse_error) in enumerate(parsed):
        if parse_error is not None or signal is None:
            raw_signal = case.get("signal")
            scenario = raw_signal.get("scenario_id") if isinstance(raw_signal, dict) else None
            report_cases.append(
                {
                    "case_id": case.get("case_id", f"case[{index}]"),
                    "scenario_id": scenario,
                    "kind": case.get("kind", "standard"),
                    "status": "failed",
                    "batch_status": "invalid_input",
                    "reasons": [parse_error or "invalid signal envelope"],
                    "unsupported_numbers": 0,
                }
            )
            continue
        item = items_by_id.get(signal.signal_id)
        if item is None:
            item = BatchItem(signal_id=signal.signal_id, status="failed", error="no batch item for signal")
        case_result, unsupported = _evaluate_case(case, item, signal)
        unsupported_total += unsupported
        if case_result["status"] == "passed":
            passed += 1
        report_cases.append(case_result)

    return EvalReport(
        dataset_version=str(dataset.get("dataset_version", DATASET_VERSION)),
        generated_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        latency_ms=latency_ms,
        total=len(raw_cases),
        passed=passed,
        unsupported_numbers=unsupported_total,
        cases=report_cases,
    )
