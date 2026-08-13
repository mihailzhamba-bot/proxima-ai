from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping
from zoneinfo import ZoneInfo

import httpx


MOSCOW = ZoneInfo("Europe/Moscow")
DEFAULT_TIMEOUT_SECONDS = 30.0
PERSONAL_SALES_INTERVAL_SECONDS = 60
SAFE_ENV_KEYS = frozenset({"WB_STATISTICS_TOKEN_FILE", "PROXIMA_RAW_DIR"})
TOKEN_CATEGORY_BITS = {
    1: "content",
    2: "analytics",
    3: "prices",
    4: "marketplace",
    5: "statistics",
    6: "promotion",
    7: "feedbacks",
    9: "buyer_chat",
    10: "supplies",
    11: "returns",
    12: "documents",
    13: "finance",
    16: "users",
}
READ_ONLY_BIT = 30
DAY1_REQUIRED_CATEGORIES = frozenset({"analytics", "prices", "statistics", "promotion", "finance"})
RATE_LIMIT_HEADERS = (
    "retry-after",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
)
ENDPOINTS = (
    ("common_ping", "https://common-api.wildberries.ru/ping", 1),
    ("seller_info", "https://common-api.wildberries.ru/api/v1/seller-info", 2),
    ("statistics_ping", "https://statistics-api.wildberries.ru/ping", 1),
)
ROOT = Path(__file__).resolve().parents[1]


class WbProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredArtifact:
    sha256: str
    byte_size: int
    path: Path


@dataclass(frozen=True)
class ProbeResult:
    receipt: dict[str, object]
    sales: list[object]


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    if not path.is_file() or path.is_symlink():
        raise WbProbeError("env file must be a regular file")
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if match is None:
            raise WbProbeError(f"invalid env syntax at line {line_number}")
        key, value = match.groups()
        if key not in SAFE_ENV_KEYS:
            raise WbProbeError(f"unsupported env key at line {line_number}: {key}")
        values[key] = value.strip().strip("'\"")
    return values


def read_token(path: Path) -> str:
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise WbProbeError("WB Statistics token file must be a regular file")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise WbProbeError("WB Statistics token file must not be accessible by group or others")
    token = path.read_text(encoding="utf-8").strip()
    if not token or any(character.isspace() for character in token):
        raise WbProbeError("WB Statistics token file must contain exactly one non-empty token")
    return token


def decode_token_claims(token: str) -> dict[str, object]:
    parts = token.split(".")
    if len(parts) != 3:
        raise WbProbeError("WB Statistics token must use JWT compact format")
    try:
        payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        payload = json.loads(payload_bytes)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise WbProbeError("WB Statistics token has an invalid JWT payload") from error
    if not isinstance(payload, dict):
        raise WbProbeError("WB Statistics token JWT payload must be an object")
    mask = payload.get("s")
    if not isinstance(mask, int) or isinstance(mask, bool) or mask < 0:
        raise WbProbeError("WB Statistics token JWT payload has no valid scope mask")
    token_type = {
        (1, None, False): "basic",
        (2, None, True): "test",
        (3, "self", False): "personal",
        (4, payload.get("for"), False): "service",
    }.get((payload.get("acc"), payload.get("for"), payload.get("t")), "unknown")
    categories = [name for bit, name in TOKEN_CATEGORY_BITS.items() if mask & (1 << bit)]
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool) or expires_at <= 0:
        raise WbProbeError("WB Statistics token JWT payload has no valid expiry")
    return {
        "type": token_type,
        "categories": categories,
        "read_only": bool(mask & (1 << READ_ONLY_BIT)),
        "expires_at": datetime.fromtimestamp(expires_at, tz=ZoneInfo("UTC")).isoformat(),
        "signature_verified_by_decode": False,
    }


def validate_day1_scope(claims: Mapping[str, object]) -> None:
    if claims.get("type") != "personal":
        raise WbProbeError("Day 1 requires a personal WB token")
    categories = claims.get("categories")
    present = set(categories) if isinstance(categories, list) and all(isinstance(value, str) for value in categories) else set()
    missing = sorted(DAY1_REQUIRED_CATEGORIES - present)
    if missing:
        raise WbProbeError(f"Day 1 token is missing required categories: {','.join(missing)}")
    if claims.get("read_only") is not True:
        raise WbProbeError("Day 1 token must be read-only")


def request_json(
    client: httpx.Client,
    *,
    name: str,
    url: str,
    token: str,
    params: Mapping[str, str] | None = None,
    max_attempts: int,
    sleep: Callable[[float], None],
) -> tuple[bytes, dict[str, str], int]:
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.get(url, params=params, headers={"Authorization": token})
        except httpx.HTTPError as error:
            if attempt == max_attempts:
                raise WbProbeError(f"{name}: network failure after {attempt} attempt(s)") from error
            sleep(PERSONAL_SALES_INTERVAL_SECONDS)
            continue

        if response.status_code == 429 and attempt < max_attempts:
            raw_retry_after = response.headers.get("Retry-After", "")
            delay = float(raw_retry_after) if raw_retry_after.isdigit() else PERSONAL_SALES_INTERVAL_SECONDS
            sleep(max(delay, PERSONAL_SALES_INTERVAL_SECONDS))
            continue
        if response.status_code != 200:
            raise WbProbeError(f"{name}: HTTP {response.status_code}")
        try:
            response.json()
        except ValueError as error:
            raise WbProbeError(f"{name}: response is not valid JSON") from error
        rate_headers = {
            header: response.headers[header]
            for header in RATE_LIMIT_HEADERS
            if header in response.headers
        }
        return response.content, rate_headers, attempt
    raise AssertionError("unreachable")


def store_immutable(output_dir: Path, content: bytes) -> StoredArtifact:
    digest = hashlib.sha256(content).hexdigest()
    parent = output_dir / "sha256" / digest[:2]
    parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(output_dir, 0o700)
    os.chmod(output_dir / "sha256", 0o700)
    os.chmod(parent, 0o700)
    destination = parent / f"{digest}.json"
    if destination.exists():
        if destination.read_bytes() != content:
            raise WbProbeError("content-addressed artifact mismatch")
        return StoredArtifact(digest, len(content), destination)

    temporary = parent / f".{digest}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.read_bytes() != content:
                raise WbProbeError("content-addressed artifact mismatch")
    finally:
        temporary.unlink(missing_ok=True)
    return StoredArtifact(digest, len(content), destination)


def validate_output_dir(output_dir: Path) -> Path:
    resolved = output_dir.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise WbProbeError("raw output directory must be outside the repository")
    return resolved


def safe_receipt_entry(
    *,
    artifact: StoredArtifact,
    status: int,
    attempts: int,
    rate_headers: Mapping[str, str],
    row_count: int | None = None,
) -> dict[str, object]:
    return {
        "http_status": status,
        "attempts": attempts,
        "sha256": artifact.sha256,
        "byte_size": artifact.byte_size,
        "artifact_path": str(artifact.path),
        "rate_limit_headers": dict(rate_headers),
        **({"row_count": row_count} if row_count is not None else {}),
    }


def run_probe(
    *,
    token_file: Path,
    output_dir: Path,
    now: datetime,
    client: httpx.Client,
    sleep: Callable[[float], None] = time.sleep,
) -> ProbeResult:
    token = read_token(token_file)
    token_claims = decode_token_claims(token)
    validate_day1_scope(token_claims)
    output_dir = validate_output_dir(output_dir)
    if now.tzinfo is None:
        raise WbProbeError("now must be timezone-aware")
    now_moscow = now.astimezone(MOSCOW)
    date_from = (now_moscow - timedelta(days=7)).replace(microsecond=0).isoformat()
    receipt: dict[str, object] = {
        "probe_version": "1",
        "retrieved_at": now_moscow.isoformat(),
        "token_ref": str(token_file),
        "token_value_recorded": False,
        "token_claims": token_claims,
        "sales_window": {
            "date_from": date_from,
            "basis": "lastChangeDate",
            "timezone": "Europe/Moscow",
        },
        "documented_limits": {
            "ping": "3 requests per 30 seconds per domain; one-off probe only",
            "seller_info_personal": "1 request per minute; burst 10",
            "sales_personal": "1 request per minute; burst 1",
        },
        "results": {},
    }
    results = receipt["results"]
    assert isinstance(results, dict)

    for name, url, max_attempts in ENDPOINTS:
        content, rate_headers, attempts = request_json(
            client,
            name=name,
            url=url,
            token=token,
            max_attempts=max_attempts,
            sleep=sleep,
        )
        artifact = store_immutable(output_dir, content)
        results[name] = safe_receipt_entry(
            artifact=artifact,
            status=200,
            attempts=attempts,
            rate_headers=rate_headers,
        )

    content, rate_headers, attempts = request_json(
        client,
        name="sales",
        url="https://statistics-api.wildberries.ru/api/v1/supplier/sales",
        token=token,
        params={"dateFrom": date_from},
        max_attempts=2,
        sleep=sleep,
    )
    sales = json.loads(content)
    if not isinstance(sales, list):
        raise WbProbeError("sales: expected a JSON array")
    artifact = store_immutable(output_dir, content)
    results["sales"] = safe_receipt_entry(
        artifact=artifact,
        status=200,
        attempts=attempts,
        rate_headers=rate_headers,
        row_count=len(sales),
    )
    return ProbeResult(receipt=receipt, sales=sales)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-off WB Day 1 API connectivity probe")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    env = read_env_file(args.env_file)
    token_file_value = args.token_file or env.get("WB_STATISTICS_TOKEN_FILE")
    output_dir_value = args.output_dir or env.get("PROXIMA_RAW_DIR")
    if token_file_value is None or output_dir_value is None:
        raise WbProbeError("set token file and output directory via arguments or .env")
    token_file = Path(token_file_value)
    output_dir = validate_output_dir(Path(output_dir_value))
    output_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    with httpx.Client(
        timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS),
        follow_redirects=False,
        headers={"User-Agent": "proxima-ai-day1-probe/1"},
    ) as client:
        result = run_probe(
            token_file=token_file,
            output_dir=output_dir,
            now=datetime.now(MOSCOW),
            client=client,
        )
    print(json.dumps({"receipt": result.receipt, "sales": result.sales}, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WbProbeError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from error
