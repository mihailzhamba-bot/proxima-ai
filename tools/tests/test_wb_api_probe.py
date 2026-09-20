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


CATEGORY_BITS = {"analytics": 2, "prices": 3, "statistics": 5, "promotion": 6, "finance": 13}
DAY1_SCOPE = (1 << 2) | (1 << 3) | (1 << 5) | (1 << 6) | (1 << 13) | (1 << 30)


def token_value(*, acc: int = 3, token_for: str | None = "self", test: bool = False, scope: int = DAY1_SCOPE) -> str:
    def encoded(value: object) -> str:
        data = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    return f"{encoded({'alg': 'none'})}.{encoded({'acc': acc, 'for': token_for, 't': test, 's': scope, 'exp': 1800000000})}.signature"


def split_token(category: str, *, read_only: bool = True, extra_bit: int | None = None) -> str:
    scope = 1 << CATEGORY_BITS[category]
    if read_only:
        scope |= 1 << 30
    if extra_bit is not None:
        scope |= 1 << extra_bit
    return token_value(scope=scope)


def split_token_files(tmp_path: Path, overrides: dict[str, str] | None = None) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for category in CATEGORY_BITS:
        path = tmp_path / f"wb_{category}_token"
        path.write_text((overrides or {}).get(category, split_token(category)) + "\n", encoding="utf-8")
        path.chmod(0o600)
        files[category] = path
    return files


def private_token_file(tmp_path: Path, token: str | None = None) -> Path:
    path = tmp_path / "wb_statistics_token"
    path.write_text((token or split_token("statistics")) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def test_probe_stores_real_payloads_but_receipt_contains_only_safe_metadata(tmp_path: Path) -> None:
    probe = load_probe()
    tokens = {category: split_token(category) for category in CATEGORY_BITS}
    token_files = split_token_files(tmp_path, tokens)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/seller-info":
            payload: object = {"name": "Sensitive Seller", "sid": "seller-id", "tin": "1234567890"}
        elif request.url.path == "/api/v1/supplier/sales":
            payload = [{"srid": "sensitive-sale-id", "date": "2026-08-12T10:00:00"}]
        else:
            payload = {"TS": "2026-08-13T12:00:00+03:00", "Status": "OK"}
        return httpx.Response(200, json=payload, headers={"X-RateLimit-Remaining": "1"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = probe.run_probe(
            token_files=token_files,
            output_dir=tmp_path / "raw",
            now=datetime.fromisoformat("2026-08-13T12:00:00+03:00"),
            client=client,
            sleep=lambda _: None,
        )

    receipt = result.receipt
    rendered = json.dumps(receipt)
    for token in tokens.values():
        assert token not in rendered
    assert "Sensitive Seller" not in rendered
    assert "sensitive-sale-id" not in rendered
    assert result.sales == [{"srid": "sensitive-sale-id", "date": "2026-08-12T10:00:00"}]
    assert receipt["results"]["sales"]["row_count"] == 1
    assert set(receipt["token_claims"]) == set(CATEGORY_BITS)
    assert receipt["token_claims"]["statistics"] == {
        "type": "personal",
        "categories": ["statistics"],
        "scope_mask": (1 << 5) | (1 << 30),
        "read_only": True,
        "expires_at": "2027-01-15T08:00:00+00:00",
        "signature_verified_by_decode": False,
    }
    assert receipt["sales_window"] == {
        "date_from": "2026-08-06T12:00:00+03:00",
        "basis": "lastChangeDate",
        "timezone": "Europe/Moscow",
    }
    assert len(requests) == 8
    expected_token_by_host = {
        "common-api.wildberries.ru": tokens["statistics"],
        "statistics-api.wildberries.ru": tokens["statistics"],
        "seller-analytics-api.wildberries.ru": tokens["analytics"],
        "finance-api.wildberries.ru": tokens["finance"],
        "discounts-prices-api.wildberries.ru": tokens["prices"],
        "advert-api.wildberries.ru": tokens["promotion"],
    }
    for request in requests:
        assert request.headers["Authorization"] == expected_token_by_host[request.url.host]
    assert {"analytics_ping", "finance_ping", "prices_ping", "promotion_ping"} <= set(receipt["results"])
    sales_request = requests[-1]
    assert sales_request.url.params["dateFrom"] == "2026-08-06T12:00:00+03:00"

    for entry in receipt["results"].values():
        artifact = Path(entry["artifact_path"])
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
            token_files=split_token_files(tmp_path),
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
    tokens = {category: split_token(category) for category in CATEGORY_BITS}

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": tokens["statistics"]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(probe.WbProbeError) as caught:
            probe.run_probe(
                token_files=split_token_files(tmp_path, tokens),
                output_dir=tmp_path / "raw",
                now=datetime.fromisoformat("2026-08-13T12:00:00+03:00"),
                client=client,
                sleep=lambda _: None,
            )

    for token in tokens.values():
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
        (token_value(acc=1, token_for=None, scope=(1 << 5) | (1 << 30)), "personal"),
        (split_token("statistics", read_only=False), "read-only"),
        (split_token("statistics", extra_bit=2), "only the statistics category"),
        (split_token("statistics", extra_bit=8), "only the statistics category"),
        (split_token("statistics", extra_bit=31), "only the statistics category"),
        (token_value(scope=DAY1_SCOPE), "only the statistics category"),
    ],
)
def test_split_token_scope_fails_closed(token: str, message: str) -> None:
    probe = load_probe()
    claims = probe.decode_token_claims(token)

    with pytest.raises(probe.WbProbeError, match=message):
        probe.validate_split_token("statistics", claims)


def test_analytics_rw_probe_token_requires_explicit_opt_in() -> None:
    probe = load_probe()
    rw_analytics = probe.decode_token_claims(split_token("analytics", read_only=False))

    with pytest.raises(probe.WbProbeError, match="read-only"):
        probe.validate_split_token("analytics", rw_analytics)
    probe.validate_split_token("analytics", rw_analytics, allow_read_write=True)
    with pytest.raises(probe.WbProbeError, match="only the analytics category"):
        probe.validate_split_token(
            "analytics",
            probe.decode_token_claims(split_token("analytics", read_only=False, extra_bit=3)),
            allow_read_write=True,
        )
    rw_statistics = probe.decode_token_claims(split_token("statistics", read_only=False))
    with pytest.raises(probe.WbProbeError, match="read-only"):
        probe.validate_split_token("statistics", rw_statistics)
    with pytest.raises(probe.WbProbeError, match="read-only"):
        probe.validate_split_token("statistics", rw_statistics, allow_read_write=True)


def test_expired_split_token_fails_closed(tmp_path: Path) -> None:
    probe = load_probe()
    expired = (
        f"{base64.urlsafe_b64encode(json.dumps({'alg': 'none'}).encode()).rstrip(b'=').decode()}."
        f"{base64.urlsafe_b64encode(json.dumps({'acc': 3, 'for': 'self', 't': False, 's': (1 << 5) | (1 << 30), 'exp': 1600000000}).encode()).rstrip(b'=').decode()}.signature"
    )
    token_files = split_token_files(tmp_path, {"statistics": expired})

    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        with pytest.raises(probe.WbProbeError, match="statistics token is expired"):
            probe.run_probe(
                token_files=token_files,
                output_dir=tmp_path / "raw",
                now=datetime.fromisoformat("2026-08-13T12:00:00+03:00"),
                client=client,
                sleep=lambda _: None,
            )


def test_day1_coverage_lists_missing_categories_and_env_keys(tmp_path: Path) -> None:
    probe = load_probe()
    files = split_token_files(tmp_path)
    del files["prices"]
    del files["promotion"]

    with pytest.raises(
        probe.WbProbeError,
        match=r"missing required categories: prices,promotion.*WB_PRICES_TOKEN_FILE,WB_PROMOTION_TOKEN_FILE",
    ):
        probe.validate_day1_coverage(files)

    with pytest.raises(probe.WbProbeError, match="does not accept token categories: content"):
        probe.validate_day1_coverage({**split_token_files(tmp_path), "content": tmp_path / "wb_content_token"})


def test_env_parser_accepts_shared_env_and_rejects_unknown_keys(tmp_path: Path) -> None:
    probe = load_probe()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "WB_STATISTICS_TOKEN_FILE=/etc/proxima-ai/secrets/wb_statistics_token",
                "WB_ANALYTICS_TOKEN_FILE=/etc/proxima-ai/secrets/wb_analytics_token",
                "WB_FINANCE_TOKEN_FILE=/etc/proxima-ai/secrets/wb_finance_token",
                "WB_PRICES_TOKEN_FILE=/etc/proxima-ai/secrets/wb_prices_token",
                "WB_PROMOTION_TOKEN_FILE=/etc/proxima-ai/secrets/wb_promotion_token",
                "PROXIMA_RAW_DIR=/srv/proxima-ai/data/day1-wb-api",
                "PROXIMA_SPOOL_DIR=/srv/proxima-ai/data/wb-analytics-spool",
                "POSTGRES_USER_FILE=/etc/proxima-ai/secrets/postgres_user",
                "POSTGRES_PASSWORD_FILE=/etc/proxima-ai/secrets/postgres_password",
                "POSTGRES_HOST=127.0.0.1",
                "POSTGRES_PORT=5432",
                "POSTGRES_DB=proxima",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    parsed = probe.read_env_file(env_file)
    assert parsed["WB_PROMOTION_TOKEN_FILE"] == "/etc/proxima-ai/secrets/wb_promotion_token"

    env_file.write_text("WB_API_KEY=must-not-be-here\n", encoding="utf-8")
    with pytest.raises(probe.WbProbeError, match="unsupported env key"):
        probe.read_env_file(env_file)


def test_probe_env_keys_cover_day2_shared_env_and_template() -> None:
    probe = load_probe()
    spec = importlib.util.spec_from_file_location("wb_async_report", ROOT / "tools" / "wb_async_report.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["wb_async_report"] = module
    spec.loader.exec_module(module)
    assert module.SAFE_ENV_KEYS <= probe.SAFE_ENV_KEYS
    template_keys = {
        line.split("=", 1)[0]
        for line in (ROOT / "infra" / "runtime.env.template").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    assert template_keys <= probe.SAFE_ENV_KEYS
    assert template_keys <= module.SAFE_ENV_KEYS


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


def test_main_reports_missing_split_tokens_from_partial_env(tmp_path: Path) -> None:
    probe = load_probe()
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"WB_STATISTICS_TOKEN_FILE={private_token_file(tmp_path)}\n"
        "WB_FINANCE_TOKEN_FILE=\n"
        f"PROXIMA_RAW_DIR={tmp_path / 'raw'}\n",
        encoding="utf-8",
    )

    with pytest.raises(probe.WbProbeError, match="missing required categories: analytics,finance,prices,promotion"):
        probe.main(["--env-file", str(env_file)])

    assert not (tmp_path / "raw").exists()


def test_main_rejects_conflicting_statistics_token_arguments(tmp_path: Path) -> None:
    probe = load_probe()
    token_file = private_token_file(tmp_path)

    with pytest.raises(probe.WbProbeError, match="not both"):
        probe.main([
            "--env-file",
            str(tmp_path / "missing.env"),
            "--token-file",
            str(token_file),
            "--statistics-token-file",
            str(token_file),
            "--output-dir",
            str(tmp_path / "raw"),
        ])
