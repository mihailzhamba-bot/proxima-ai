"""Batch orchestration: per-signal retry, timeout, rollback flag, deterministic checks, audit."""

from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import asdict
from datetime import datetime, timezone
from importlib import resources
from typing import Any

from proxima_control_plane.diagnosis.adapters.base import LLMClient
from proxima_control_plane.diagnosis.adapters.factory import create_client
from proxima_control_plane.diagnosis.audit import AuditLog
from proxima_control_plane.diagnosis.config import DiagnosisConfig
from proxima_control_plane.diagnosis.models import (
    BatchItem,
    BatchResult,
    Diagnosis,
    DiagnosisInput,
)
from proxima_control_plane.diagnosis.prompts.builder import (
    PROMPT_VERSION,
    build_messages,
    collect_numbers,
)
from proxima_control_plane.diagnosis.validator import validate_diagnosis

MAX_RETRIES = 2

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_TEXT_KEYS = frozenset({"hypothesis", "question", "why_it_matters", "confidence_note"})

_SCHEMA: dict[str, Any] | None = None


def _schema() -> dict[str, Any]:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(
            resources.files("proxima_control_plane.diagnosis")
            .joinpath("schema", "diagnosis.draft.v1.json")
            .read_text(encoding="utf-8")
        )
    return _SCHEMA


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _input_sha256(signal: DiagnosisInput) -> str:
    canonical = json.dumps(asdict(signal), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _content_strings(value: Any, acc: list[str]) -> list[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _TEXT_KEYS and isinstance(item, str):
                acc.append(item)
            else:
                _content_strings(item, acc)
    elif isinstance(value, list):
        for item in value:
            _content_strings(item, acc)
    return acc


def _determinism_errors(obj: dict[str, Any], signal: DiagnosisInput) -> list[str]:
    errors: list[str] = []
    allowed_numbers = {
        float(number)
        for numbers in (
            collect_numbers(signal.payload, "payload"),
            collect_numbers(signal.context_extracts, "context_extracts"),
        )
        for number in numbers.values()
    }
    for text in _content_strings(obj, []):
        for token in _NUMBER_RE.findall(text):
            if float(token) not in allowed_numbers:
                errors.append(f"number {token} is not present in the input")
    allowed_refs = set(signal.source_refs)
    used_refs: set[str] = set()
    for cause in [obj["primary_cause"], *obj["alternatives"]]:
        used_refs.update(cause["source_refs"])
    for ref in sorted(used_refs - allowed_refs):
        errors.append(f"source_ref {ref!r} is not present in the input")
    return errors


def _attempt(
    client: LLMClient,
    system: str,
    user: str,
    schema: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(client.diagnose, system, user, schema)
        return future.result(timeout=timeout_seconds)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _diagnose_signal(
    client: LLMClient,
    signal: DiagnosisInput,
    system: str,
    user: str,
    schema: dict[str, Any],
    timeout_seconds: int,
) -> tuple[str, dict[str, Any] | None, str | None, int]:
    last_error: str | None = None
    attempts = 0
    for attempt in range(1, MAX_RETRIES + 2):
        attempts = attempt
        try:
            obj = _attempt(client, system, user, schema, timeout_seconds)
        except FutureTimeoutError:
            return "timeout", None, f"llm call exceeded timeout of {timeout_seconds}s", attempts
        except Exception as exc:
            last_error = f"llm call failed: {exc}"
            continue
        errors = [*validate_diagnosis(obj), *_determinism_errors(obj, signal)]
        if not errors:
            return "ok", obj, None, attempts
        last_error = "; ".join(errors)
    return "failed", None, last_error, attempts


def run_batch(
    signals: list[DiagnosisInput],
    config: DiagnosisConfig,
    *,
    client: LLMClient | None = None,
) -> BatchResult:
    """Process signals one by one; per-signal failures isolate into failed/timeout items.

    client=None builds the provider client from config (only when llm_enabled).
    """
    audit = AuditLog(config.audit_path)
    active = client if client is not None else (create_client(config) if config.llm_enabled else None)
    items: list[BatchItem] = []
    generated_at = _now_iso()

    for signal in signals:
        started = time.monotonic()
        attempts = 0
        if not config.llm_enabled:
            outcome, obj, error = "skipped_flag", None, None
        else:
            system, user, _version = build_messages(signal)
            outcome, obj, error, attempts = _diagnose_signal(
                active, signal, system, user, _schema(), config.timeout_seconds
            )
        latency_ms = int((time.monotonic() - started) * 1000)

        if outcome == "ok":
            diagnosis = Diagnosis(
                signal_id=obj["signal_id"],
                scenario_id=obj["scenario_id"],
                trust=obj["trust"],
                primary_cause=obj["primary_cause"],
                alternatives=obj["alternatives"],
                unknowns=obj["unknowns"],
                confidence_note=obj["confidence_note"],
                model=obj["model"],
                prompt_version=obj["prompt_version"],
                generated_at=obj["generated_at"],
            )
            items.append(BatchItem(signal_id=signal.signal_id, status="ok", diagnosis=diagnosis))
        else:
            items.append(BatchItem(signal_id=signal.signal_id, status=outcome, error=error))

        audit.record(
            {
                "ts": _now_iso(),
                "signal_id": signal.signal_id,
                "scenario_id": signal.scenario_id,
                "input_sha256": _input_sha256(signal),
                "model": config.model if active is None else getattr(active, "model", config.model),
                "prompt_version": PROMPT_VERSION,
                "outcome": outcome,
                "attempts": attempts,
                "latency_ms": latency_ms,
            }
        )

    return BatchResult(generated_at=generated_at, items=items)
