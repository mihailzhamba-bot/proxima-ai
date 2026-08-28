from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
from typing import Iterator


_ID = re.compile(r"[0-9a-f]{64}\Z")


def _canonical(value: object) -> object:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("authority payload keys must be strings")
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if value is None or type(value) in {str, int, bool}:
        return value
    raise ValueError("authority payload type is unsupported")


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("short authority journal write")
        offset += written


class AuthorityJournal:
    """One crash-durable, identity-bound journal for a supervised operation.

    The journal deliberately records only typed phases.  A caller cannot use it
    as a generic log or make a completed operation execute another effect.
    """

    def __init__(self, common_dir: Path, operation_id: str) -> None:
        if not _ID.fullmatch(operation_id):
            raise ValueError("authority operation id is invalid")
        self.operation_id = operation_id
        self.root = common_dir.resolve() / "now" / "authority"
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("authority journal root must not be a symlink")
        self.path = self.root / f"{operation_id}.jsonl"
        self.lock_path = self.root / "authority.lock"

    @contextmanager
    def locked(self) -> Iterator[None]:
        descriptor = os.open(self.lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def events(self) -> tuple[dict[str, object], ...]:
        if not self.path.exists():
            return ()
        if self.path.is_symlink():
            raise ValueError("authority journal must not be a symlink")
        descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            raw = os.read(descriptor, os.fstat(descriptor).st_size).decode("utf-8")
        finally:
            os.close(descriptor)
        try:
            events = tuple(json.loads(line) for line in raw.splitlines() if line)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("authority journal is malformed") from error
        if not all(isinstance(event, dict) and type(event.get("event")) is str for event in events):
            raise ValueError("authority journal is malformed")
        return events

    def _append(self, event: str, **payload: object) -> None:
        line = json.dumps(
            {"at": datetime.now(UTC).isoformat(), "event": event, **_canonical(payload)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode() + b"\n"
        descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            _write_all(descriptor, line)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def open(self, identity: dict[str, object]) -> None:
        canonical = _canonical(identity)
        if not isinstance(canonical, dict) or not canonical:
            raise ValueError("authority identity is invalid")
        events = self.events()
        opened = [event for event in events if event.get("event") == "OPENED"]
        if len(opened) > 1:
            raise ValueError("authority journal has duplicate OPENED records")
        if not opened:
            if events:
                raise ValueError("authority journal begins without OPENED record")
            self._append("OPENED", identity=canonical)
            return
        if opened[0].get("identity") != canonical:
            raise ValueError("authority journal identity mismatch")

    def _step(self, kind: str, step: str) -> dict[str, object] | None:
        values = [event for event in self.events() if event.get("event") == kind and event.get("step") == step]
        if len(values) > 1:
            raise ValueError(f"authority journal has duplicate {kind} for {step}")
        return values[0] if values else None

    def intent(self, step: str, binding: dict[str, object]) -> dict[str, object] | None:
        if not isinstance(step, str) or not step or self.complete() is not None:
            raise ValueError("authority intent is invalid after completion")
        existing = self._step("INTENT", step)
        canonical = _canonical(binding)
        if existing:
            if existing.get("binding") != canonical:
                raise ValueError("authority intent binding mismatch")
            return existing
        self._append("INTENT", step=step, binding=canonical)
        return None

    def effect(self, step: str, receipt: dict[str, object]) -> dict[str, object] | None:
        intent = self._step("INTENT", step)
        if intent is None:
            raise ValueError("authority effect has no prior intent")
        existing = self._step("EFFECT", step)
        canonical = _canonical(receipt)
        if existing:
            if existing.get("receipt") != canonical:
                raise ValueError("authority effect receipt mismatch")
            return existing
        self._append("EFFECT", step=step, receipt=canonical)
        return None

    def effect_receipt(self, step: str) -> dict[str, object] | None:
        event = self._step("EFFECT", step)
        receipt = event.get("receipt") if event else None
        return receipt if isinstance(receipt, dict) else None

    def complete(self, receipt: dict[str, object] | None = None) -> dict[str, object] | None:
        completed = [event for event in self.events() if event.get("event") == "COMPLETE"]
        if len(completed) > 1:
            raise ValueError("authority journal has duplicate COMPLETE records")
        if completed:
            existing = completed[0].get("receipt")
            if not isinstance(existing, dict):
                raise ValueError("authority completion receipt is malformed")
            if receipt is not None and existing != _canonical(receipt):
                raise ValueError("authority completion receipt mismatch")
            return existing
        if receipt is not None:
            self._append("COMPLETE", receipt=receipt)
            return _canonical(receipt)  # type: ignore[return-value]
        return None

    @staticmethod
    def digest(value: object) -> str:
        return sha256(json.dumps(_canonical(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
