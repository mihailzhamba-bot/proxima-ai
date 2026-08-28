from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
import fcntl
import json
import os
from pathlib import Path
import re
from typing import Iterator

_ID = re.compile(r"[0-9a-f]{64}\Z")


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("short provenance write")
        offset += written


class ProvenanceJournal:
    """Append-only WAL for one dispatch identity below Git common-dir."""

    def __init__(self, common_dir: Path, operation_id: str) -> None:
        if not _ID.fullmatch(operation_id):
            raise ValueError("dispatch operation id is invalid")
        self.root = common_dir.absolute() / "now" / "provenance"
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("provenance root must not be a symlink")
        self.path = self.root / f"{operation_id}.jsonl"
        self.lock_path = self.root / f"{operation_id}.lock"

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
        descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            raw = os.read(descriptor, os.fstat(descriptor).st_size).decode("utf-8")
        finally:
            os.close(descriptor)
        try:
            events = tuple(json.loads(line) for line in raw.splitlines() if line)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("dispatch provenance is malformed") from error
        if not all(isinstance(event, dict) for event in events):
            raise ValueError("dispatch provenance is malformed")
        return events

    def append(self, event: str, **payload: object) -> None:
        if not isinstance(event, str) or not event:
            raise ValueError("provenance event is invalid")
        normalized = {
            key: asdict(value) if is_dataclass(value) else value
            for key, value in payload.items()
        }
        line = (json.dumps({"at": datetime.now(UTC).isoformat(), "event": event, **normalized}, sort_keys=True, separators=(",", ":")) + "\n").encode()
        descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            _write_all(descriptor, line)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def success(self) -> dict[str, object] | None:
        successes = [event for event in self.events() if event.get("event") == "dispatch_succeeded"]
        if len(successes) > 1:
            raise ValueError("duplicate dispatch success provenance")
        return successes[0] if successes else None
