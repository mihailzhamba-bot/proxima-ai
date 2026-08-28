from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Iterator
from uuid import uuid4

_TOKEN = re.compile(r"[0-9a-f]{64}\Z")

def _now() -> str:
    return datetime.now().astimezone().isoformat()

def normalize_zones(zones: tuple[str, ...]) -> tuple[str, ...]:
    if not zones: raise ValueError("zones must be non-empty")
    result: list[str] = []
    for zone in zones:
        if not isinstance(zone, str) or not zone or zone.strip() != zone or any(mark in zone for mark in "*?["): raise ValueError("zone must be a non-empty resolved path")
        path = PurePosixPath(zone)
        if path.is_absolute() or str(path) in {".", "/"} or ".." in path.parts: raise ValueError("zone must be a repo-relative non-root path")
        if str(path) not in result: result.append(str(path))
    return tuple(result)

def _overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/")

def _no_symlink(path: Path) -> None:
    if path.is_symlink(): raise ValueError(f"symlink runtime path: {path}")

def _fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)

@dataclass(frozen=True)
class ClaimRequest:
    key: str; track: str; zones: tuple[str, ...]; owner: str; run_id: str; task_id: str; worker_id: str; snapshot_version: str; captured_at: str; snapshot_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_digest, str) or not _TOKEN.fullmatch(self.snapshot_digest):
            raise ValueError("snapshot_digest must be canonical lowercase SHA-256")

@dataclass(frozen=True)
class Claim:
    token: str; key: str; track: str; zones: tuple[str, ...]; owner: str; run_id: str; task_id: str; worker_id: str; snapshot_version: str; captured_at: str; snapshot_digest: str; created_at: str

@dataclass(frozen=True)
class ClaimResult:
    claim: Claim | None; reason: str | None = None; resumed: bool = False

@dataclass(frozen=True)
class Lease:
    token: str; owner: str; run_id: str; task_id: str; worker_id: str; created_at: str

@dataclass(frozen=True)
class LeaseResult:
    lease: Lease | None; reason: str | None = None

@dataclass(frozen=True)
class LivenessEvidence:
    token: str; owner_live: bool; task_live: bool; worker_live: bool; owner_locator: str; task_locator: str; worker_locator: str; captured_at: datetime
    def valid_for(self, token: str, *, clock: callable, max_age: timedelta, future_skew: timedelta) -> bool:
        if not (self.token == token and bool(_TOKEN.fullmatch(self.token)) and self.owner_live is False and self.task_live is False and self.worker_live is False and all(isinstance(item, str) and item for item in (self.owner_locator, self.task_locator, self.worker_locator)) and isinstance(self.captured_at, datetime) and self.captured_at.tzinfo is not None): return False
        now = clock()
        if not isinstance(now, datetime) or now.tzinfo is None: return False
        delta = now.astimezone(UTC) - self.captured_at.astimezone(UTC)
        return -future_skew <= delta <= max_age

def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written <= 0: raise OSError("short write")
        offset += written

class ClaimStore:
    def __init__(self, common_dir: Path) -> None:
        self.common_dir = common_dir.absolute()
        if self.common_dir.name != ".git" or not self.common_dir.is_dir(): raise ValueError("Git common-dir is invalid")
        _no_symlink(self.common_dir)
        self.root, self.claims_dir = self.common_dir / "now", self.common_dir / "now" / "claims"
        for directory in (self.root, self.claims_dir):
            if directory.exists() or directory.is_symlink(): _no_symlink(directory)
            else:
                try: directory.mkdir()
                except FileExistsError: _no_symlink(directory)
                _fsync_dir(directory.parent)
        self.audit_path, self.lease_path, self.lock_path = self.root / "audit.jsonl", self.root / "integration.json", self.root / "lock"
        self._reject_residue()

    def _reject_residue(self) -> None:
        for directory in (self.root, self.claims_dir):
            _no_symlink(directory)
            if any(path.name.endswith(".tmp") for path in directory.iterdir()): raise ValueError("crash residue in runtime evidence")
        if self.audit_path.exists():
            pending: set[str] = set()
            try:
                for line in self.audit_path.read_text(encoding="utf-8").splitlines():
                    event = json.loads(line)
                    if event.get("event") == "integration_recovery_intent": pending.add(event["token"])
                    if event.get("event") == "integration_recovered": pending.discard(event["token"])
            except (OSError, KeyError, TypeError, json.JSONDecodeError) as error: raise ValueError("invalid runtime audit evidence") from error
            if pending: raise ValueError("incomplete recovery intent")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        _no_symlink(self.root)
        descriptor = os.open(self.lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX); self._reject_residue(); yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN); os.close(descriptor)

    def _audit(self, event: str, **payload: object) -> None:
        data = (json.dumps({"at": _now(), "event": event, **payload}, sort_keys=True, separators=(",", ":")) + "\n").encode()
        descriptor = os.open(self.audit_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try: _write_all(descriptor, data); os.fsync(descriptor)
        finally: os.close(descriptor)
        _fsync_dir(self.root)

    def _child(self, directory: Path, token: str) -> Path | None:
        if not isinstance(token, str) or not _TOKEN.fullmatch(token): return None
        path = directory / f"{token}.json"
        return path if path.parent == directory and path.resolve(strict=False).parent == directory.resolve() else None

    def _publish(self, directory: Path, target: Path, payload: dict[str, object]) -> bool:
        temporary = directory / f".{target.name}.{uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try: _write_all(descriptor, json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()); os.fsync(descriptor)
        finally: os.close(descriptor)
        try: os.link(temporary, target); _fsync_dir(directory); return True
        except FileExistsError: return False
        finally: temporary.unlink(missing_ok=True); _fsync_dir(directory)

    def _claims(self) -> tuple[Claim, ...]:
        result: list[Claim] = []
        for path in sorted(self.claims_dir.iterdir()):
            if path.name.endswith(".tmp"): raise ValueError("crash residue in runtime evidence")
            if path.is_symlink() or path.suffix != ".json" or self._child(self.claims_dir, path.stem) != path: raise ValueError("invalid claim evidence")
            try: claim = Claim(**{**json.loads(path.read_text(encoding="utf-8")), "zones": tuple(json.loads(path.read_text(encoding="utf-8"))["zones"])})
            except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error: raise ValueError("invalid claim evidence") from error
            if claim.token != path.stem or not _TOKEN.fullmatch(claim.token): raise ValueError("invalid claim evidence")
            result.append(claim)
        return tuple(result)

    def claim(self, request: ClaimRequest) -> ClaimResult:
        if request.track not in {"A", "B", "C"} or not request.key or not all(isinstance(value, str) and value for value in (request.owner, request.run_id, request.task_id, request.worker_id, request.snapshot_version, request.captured_at)) or not _TOKEN.fullmatch(request.snapshot_digest): return ClaimResult(None, "claim identity is invalid")
        try: zones = normalize_zones(request.zones)
        except ValueError as error: return ClaimResult(None, str(error))
        with self._locked():
            claims = self._claims()
            existing = next((item for item in claims if item.key == request.key), None)
            identity = (request.key, request.track, zones, request.owner, request.run_id, request.task_id, request.worker_id, request.snapshot_version, request.captured_at, request.snapshot_digest)
            if existing:
                if identity == (existing.key, existing.track, existing.zones, existing.owner, existing.run_id, existing.task_id, existing.worker_id, existing.snapshot_version, existing.captured_at, existing.snapshot_digest): return ClaimResult(existing, resumed=True)
                return ClaimResult(None, "claim provenance conflict")
            if any(item.track == request.track for item in claims): return ClaimResult(None, "same-track active claim")
            for item in claims:
                for left in item.zones:
                    for right in zones:
                        if _overlap(left, right):
                            first, second = (left, right) if len(left.split("/")) <= len(right.split("/")) else (right, left)
                            return ClaimResult(None, f"zone overlap: {first} <-> {second}")
            token = sha256("\0".join((request.key, request.track, *zones, request.owner, request.run_id, request.task_id, request.worker_id, request.snapshot_version, request.captured_at, request.snapshot_digest)).encode()).hexdigest()
            claim = Claim(token, *identity, _now()); path = self._child(self.claims_dir, token); assert path
            if not self._publish(self.claims_dir, path, {**asdict(claim), "zones": list(claim.zones)}): return ClaimResult(None, "claim token collision")
            self._audit("claim_created", token=token, key=request.key, track=request.track); return ClaimResult(claim)

    def release(self, token: str, owner: str) -> bool:
        path = self._child(self.claims_dir, token)
        if path is None: return False
        with self._locked():
            if not path.is_file() or path.is_symlink(): return False
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("token") != token or data.get("owner") != owner: return False
            path.unlink(); _fsync_dir(self.claims_dir); self._audit("claim_released", token=token, owner=owner); return True

    def acquire_integration(self, owner: str, run_id: str, task_id: str, worker_id: str) -> LeaseResult:
        if not all(isinstance(value, str) and value for value in (owner, run_id, task_id, worker_id)): return LeaseResult(None, "integration identity is invalid")
        with self._locked():
            if self.lease_path.exists():
                if self.lease_path.is_symlink(): raise ValueError("invalid integration evidence")
                lease = Lease(**json.loads(self.lease_path.read_text(encoding="utf-8")))
                return LeaseResult(lease) if (lease.owner, lease.run_id, lease.task_id, lease.worker_id) == (owner, run_id, task_id, worker_id) else LeaseResult(None, "integration lease active")
            token = sha256(f"integration\0{owner}\0{run_id}\0{task_id}\0{worker_id}".encode()).hexdigest(); lease = Lease(token, owner, run_id, task_id, worker_id, _now())
            if not self._publish(self.root, self.lease_path, asdict(lease)): return LeaseResult(None, "integration lease active")
            self._audit("integration_acquired", token=token, owner=owner, run_id=run_id); return LeaseResult(lease)

    def release_integration(self, token: str, owner: str) -> bool:
        if not _TOKEN.fullmatch(token): return False
        with self._locked():
            if not self.lease_path.is_file() or self.lease_path.is_symlink(): return False
            lease = Lease(**json.loads(self.lease_path.read_text(encoding="utf-8")))
            if lease.token != token or lease.owner != owner: return False
            self.lease_path.unlink(); _fsync_dir(self.root); self._audit("integration_released", token=token, owner=owner); return True

    def recover_integration(self, evidence: LivenessEvidence, *, clock: callable = lambda: datetime.now(UTC), max_age: timedelta = timedelta(minutes=5), future_skew: timedelta = timedelta(seconds=30)) -> bool:
        with self._locked():
            if not self.lease_path.is_file() or self.lease_path.is_symlink(): return False
            lease = Lease(**json.loads(self.lease_path.read_text(encoding="utf-8")))
            if not evidence.valid_for(lease.token, clock=clock, max_age=max_age, future_skew=future_skew): return False
            self._audit("integration_recovery_intent", token=lease.token, owner_locator=evidence.owner_locator, task_locator=evidence.task_locator, worker_locator=evidence.worker_locator, liveness_captured_at=evidence.captured_at.isoformat())
            self.lease_path.unlink(); _fsync_dir(self.root)
            self._audit("integration_recovered", token=lease.token, owner_locator=evidence.owner_locator, task_locator=evidence.task_locator, worker_locator=evidence.worker_locator, liveness_captured_at=evidence.captured_at.isoformat()); return True
