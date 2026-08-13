from __future__ import annotations

import importlib.util
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_probe():
    spec = importlib.util.spec_from_file_location("wb_api_probe", ROOT / "tools" / "wb_api_probe.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["wb_api_probe"] = module
    spec.loader.exec_module(module)
    return module


DAY1_SCOPE = (1 << 2) | (1 << 3) | (1 << 5) | (1 << 6) | (1 << 13) | (1 << 30)


def token_value(*, acc: int = 3, token_for: str | None = "self", test: bool = False, scope: int = DAY1_SCOPE) -> str:
    def encoded(value: object) -> str:
        data = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    return f"{encoded({'alg': 'none'})}.{encoded({'acc': acc, 'for': token_for, 't': test, 's': scope, 'exp': 1800000000})}.signature"


def private_token_file(tmp_path: Path, token: str | None = None) -> Path:
    path = tmp_path / "wb_statistics_token"
    path.write_text((token or token_value()) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def test_probe_stores_real_payloads_but_receipt_contains_only_safe_metadata(tmp_path: Path) -> None:
    probe = load_probe()
    token = token_value()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/seller-info":
            payload = {"name": "Sensitive Seller", "sid": "seller-id", "tin": "1234567890"}
        elif request.url.path == "/api/v1/supplier/sales":
            payload = [{"srid": "sensitive-sale-id", "date": "2026-08-12T10:00:00"}]
        else:
            payload = {"TS": "2026-08-13T12:00:00+03:00", "Status": "OK"}
        return httpx.Response(200, json=payload, headers={"X-RateLimit-Remaining": "1"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = probe.run_probe(
            token_file=private_token_file(tmp_path, token),
            output_dir=tmp_path / "raw",
            now=datetime.fromisoformat("2026-08-13T12:00:00+03:00"),
            client=client,
            sleep=lambda _: None,
        )

    receipt = result.receipt
    rendered = json.dumps(receipt)
    assert token not in rendered
    assert "Sensitive Seller" not in rendered
    assert "sensitive-sale-id" not in rendered
    assert result.sales == [{"srid": "sensitive-sale-id", "date": "2026-08-12T10:00:00"}]
    assert receipt["results"]["sales"]["row_count"] == 1
    assert receipt["token_claims"] == {
        "type": "personal",
        "categories": ["analytics", "prices", "statistics", "promotion", "finance"],
        "read_only": True,
        "expires_at": "2027-01-15T08:00:00+00:00",
        "signature_verified_by_decode": False,
    }
    assert receipt["sales_window"] == {
        "date_from": "2026-08-06T12:00:00+03:00",
        "basis": "lastChangeDate",
        "timezone": "Europe/Moscow",
    }
    assert len(requests) == 4
    assert all(request.headers["Authorization"] == token for request in requests)
    sales_request = requests[-1]
    assert sales_request.url.params["dateFrom"] == "2026-08-06T12:00:00+03:00"

    for result in receipt["results"].values():
        artifact = Path(result["artifact_path"])
        assert artifact.exists()
        assert (artifact.stat().st_mode & 0o777) == 0o600


def test_sales_429_waits_at_least_documented_personal_interval(tmp_path: Path) -> None:
    probe = load_probe()
    sales_attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sales_attempts
        if request.url.path == "/api/v1/supplier/sales":
            sales_attempts += 1
            if sales_attempts == 1:
                return httpx.Response(429, json={"detail": "rate limited"}, headers={"Retry-After": "5"})
            return httpx.Response(200, json=[])
        if request.url.path == "/api/v1/seller-info":
            return httpx.Response(200, json={"name": "Seller"})
        return httpx.Response(200, json={"Status": "OK"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = probe.run_probe(
            token_file=private_token_file(tmp_path),
            output_dir=tmp_path / "raw",
            now=datetime.fromisoformat("2026-08-13T12:00:00+03:00"),
            client=client,
            sleep=delays.append,
        )

    assert sales_attempts == 2
    assert delays == [60]
    assert result.receipt["results"]["sales"]["attempts"] == 2


def test_auth_error_never_includes_token_or_response_body(tmp_path: Path) -> None:
    probe = load_probe()
    token = token_value()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": token})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(probe.WbProbeError) as caught:
            probe.run_probe(
                token_file=private_token_file(tmp_path, token),
                output_dir=tmp_path / "raw",
                now=datetime.fromisoformat("2026-08-13T12:00:00+03:00"),
                client=client,
                sleep=lambda _: None,
            )

    assert token not in str(caught.value)
    assert str(caught.value) == "common_ping: HTTP 401"


def test_token_file_permissions_fail_closed(tmp_path: Path) -> None:
    probe = load_probe()
    token_file = private_token_file(tmp_path)
    token_file.chmod(0o644)

    with pytest.raises(probe.WbProbeError, match="group or others"):
        probe.read_token(token_file)


@pytest.mark.parametrize(
    ("token", "message"),
    [
        (token_value(acc=1, token_for=None), "personal"),
        (token_value(scope=DAY1_SCOPE & ~(1 << 5)), "statistics"),
        (token_value(scope=DAY1_SCOPE & ~(1 << 30)), "read-only"),
    ],
)
def test_day1_token_scope_fails_closed(tmp_path: Path, token: str, message: str) -> None:
    probe = load_probe()
    claims = probe.decode_token_claims(token)

    with pytest.raises(probe.WbProbeError, match=message):
        probe.validate_day1_scope(claims)


def test_env_parser_rejects_token_value_and_unknown_keys(tmp_path: Path) -> None:
    probe = load_probe()
    env_file = tmp_path / ".env"
    env_file.write_text("WB_API_KEY=must-not-be-here\n", encoding="utf-8")

    with pytest.raises(probe.WbProbeError, match="unsupported env key"):
        probe.read_env_file(env_file)


def test_raw_output_inside_repository_fails_closed() -> None:
    probe = load_probe()

    with pytest.raises(probe.WbProbeError, match="outside the repository"):
        probe.validate_output_dir(ROOT / "raw" / "day1")


def test_main_rejects_repository_raw_path_before_creating_it(tmp_path: Path) -> None:
    probe = load_probe()
    unsafe = ROOT / "raw" / f"day1-{tmp_path.name}"
    assert not unsafe.exists()

    with pytest.raises(probe.WbProbeError, match="outside the repository"):
        probe.main([
            "--token-file",
            str(private_token_file(tmp_path)),
            "--output-dir",
            str(unsafe),
        ])

    assert not unsafe.exists()
