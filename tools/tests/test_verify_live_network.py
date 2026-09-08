"""Гейт `tools/verify_live_network.py` (AD-4): проходит на репозитории и падает при дрейфе."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FLAG_LINE = '      WB_ALLOW_LIVE_NETWORK: "1"\n'


def load_gate():
    path = ROOT / "tools" / "verify_live_network.py"
    spec = importlib.util.spec_from_file_location("verify_live_network", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_live_network"] = module
    spec.loader.exec_module(module)
    return module


def compose_copy(tmp_path: Path, transform) -> Path:
    original = (ROOT / "infra" / "compose.yaml").read_text(encoding="utf-8")
    assert original.count(FLAG_LINE) == 1
    drifted = tmp_path / "compose.yaml"
    drifted.write_text(transform(original), encoding="utf-8")
    return drifted


def test_live_network_gate_passes_on_the_repository() -> None:
    gate = load_gate()
    summary = gate.verify()
    assert summary["collector"] == "1"
    assert summary["other_services"] == 3
    assert summary["units"] >= 13
    assert summary["test_files"] >= 2


def test_compose_collector_opt_in_accepts_string_or_int_and_needs_the_ad4_note(tmp_path: Path) -> None:
    gate = load_gate()
    as_int = compose_copy(tmp_path, lambda text: text.replace(FLAG_LINE, "      WB_ALLOW_LIVE_NETWORK: 1\n"))
    assert gate.check_compose(compose=as_int)["collector"] == "1"

    missing = compose_copy(tmp_path, lambda text: text.replace(FLAG_LINE, ""))
    with pytest.raises(AssertionError, match="`collector` must set WB_ALLOW_LIVE_NETWORK"):
        gate.check_compose(compose=missing)

    off = compose_copy(tmp_path, lambda text: text.replace(FLAG_LINE, '      WB_ALLOW_LIVE_NETWORK: "0"\n'))
    with pytest.raises(AssertionError, match="`collector` must set WB_ALLOW_LIVE_NETWORK"):
        gate.check_compose(compose=off)

    unexplained = compose_copy(tmp_path, lambda text: text.replace("      # AD-4: the WB transport is fail-closed", "      # the WB transport is fail-closed"))
    with pytest.raises(AssertionError, match="AD-4 note"):
        gate.check_compose(compose=unexplained)


def test_compose_rejects_the_flag_on_control_plane_services(tmp_path: Path) -> None:
    gate = load_gate()
    leaked = compose_copy(
        tmp_path,
        lambda text: text.replace("      NORM_DATABASE_URI_FILE: /run/secrets/proxima_norm_uri\n", "      NORM_DATABASE_URI_FILE: /run/secrets/proxima_norm_uri\n" + FLAG_LINE),
    )
    with pytest.raises(AssertionError, match="`control-plane` must not set"):
        gate.check_compose(compose=leaked)

    admin = compose_copy(
        tmp_path,
        lambda text: text.replace("      WB_ANALYTICS_TOKEN_FILE: /run/secrets/amirova-test_wb_analytics_token\n", "      WB_ANALYTICS_TOKEN_FILE: /run/secrets/amirova-test_wb_analytics_token\n" + FLAG_LINE),
    )
    with pytest.raises(AssertionError, match="`control-plane-admin` must not set"):
        gate.check_compose(compose=admin)


def test_env_files_may_mention_the_flag_in_a_comment_only(tmp_path: Path) -> None:
    gate = load_gate()
    jobs_env = tmp_path / "jobs.env"
    jobs_env.write_text((ROOT / "infra" / "jobs.env").read_text(encoding="utf-8") + "WB_ALLOW_LIVE_NETWORK=1\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="must not be set in env files"):
        gate.check_env_files(jobs_env=jobs_env)

    example = tmp_path / "local.env.example"
    example.write_text("# WB_ALLOW_LIVE_NETWORK=1 only in the collector job container\nPROXIMA_RAW_DIR=/srv/proxima-ai/raw\n", encoding="utf-8")
    gate.check_env_files(example=example)
    example.write_text("export WB_ALLOW_LIVE_NETWORK='1'\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="must not be set in env files"):
        gate.check_env_files(example=example)


def test_safe_env_keys_must_not_admit_the_flag(tmp_path: Path) -> None:
    gate = load_gate()
    original = (ROOT / "tools" / "wb_async_report.py").read_text(encoding="utf-8")
    widened = tmp_path / "wb_async_report.py"
    widened.write_text(original.replace('        "PROXIMA_SPOOL_DIR",\n', '        "PROXIMA_SPOOL_DIR",\n        "WB_ALLOW_LIVE_NETWORK",\n', 1), encoding="utf-8")
    with pytest.raises(AssertionError, match="SAFE_ENV_KEYS must not admit"):
        gate.check_env_files(wb_async_report=widened)


def test_systemd_units_must_not_carry_the_flag(tmp_path: Path) -> None:
    gate = load_gate()
    units = tmp_path / "systemd"
    shutil.copytree(ROOT / "infra" / "systemd", units)
    assert gate.check_systemd(systemd=units) >= 13

    morning = units / "proxima-morning@.service"
    morning.write_text(morning.read_text(encoding="utf-8").replace("[Service]\n", "[Service]\nEnvironment=WB_ALLOW_LIVE_NETWORK=1\n", 1), encoding="utf-8")
    with pytest.raises(AssertionError, match="proxima-morning@.service:.*must not come from a systemd unit"):
        gate.check_systemd(systemd=units)

    morning.write_text(morning.read_text(encoding="utf-8").replace("Environment=WB_ALLOW_LIVE_NETWORK=1\n", "# Environment=WB_ALLOW_LIVE_NETWORK=1\n"), encoding="utf-8")
    drop_in = units / "proxima-funnel-v3@.service.d" / "20-live.conf"
    drop_in.write_text("[Service]\nEnvironment=WB_ALLOW_LIVE_NETWORK=1\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="20-live.conf:2: WB_ALLOW_LIVE_NETWORK must not come from a systemd unit"):
        gate.check_systemd(systemd=units)


def test_tests_stay_network_free_except_the_restoring_seam_test(tmp_path: Path) -> None:
    gate = load_gate()
    tests = tmp_path / "services" / "collector" / "tests"
    tests.mkdir(parents=True)
    (tests / "fixture.test.ts").write_text("// WB_ALLOW_LIVE_NETWORK=1 is never set here\nconst previous = process.env.WB_ALLOW_LIVE_NETWORK;\ndelete process.env.WB_ALLOW_LIVE_NETWORK;\n", encoding="utf-8")
    assert gate.check_tests(test_dirs=(tests,), root=tmp_path) == 1

    for source in (
        "process.env.WB_ALLOW_LIVE_NETWORK = '1';\n",
        "process.env['WB_ALLOW_LIVE_NETWORK'] = \"1\";\n",
        "spawnSync('npm', [], { env: { WB_ALLOW_LIVE_NETWORK: '1' } });\n",
        "vi.stubEnv('WB_ALLOW_LIVE_NETWORK', '1');\n",
        "execSync('WB_ALLOW_LIVE_NETWORK=1 npm run collect');\n",
    ):
        (tests / "live.test.ts").write_text(source, encoding="utf-8")
        with pytest.raises(AssertionError, match="live.test.ts:1: a test must not set WB_ALLOW_LIVE_NETWORK=1"):
            gate.check_tests(test_dirs=(tests,), root=tmp_path)
    (tests / "live.test.ts").unlink()

    seam = tests / "wb-client.test.ts"
    seam.write_text("process.env.WB_ALLOW_LIVE_NETWORK = '1';\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="seam test must restore"):
        gate.check_tests(test_dirs=(tests,), root=tmp_path)
    seam.write_text("try {\n  process.env.WB_ALLOW_LIVE_NETWORK = '1';\n} finally {\n  delete process.env.WB_ALLOW_LIVE_NETWORK;\n}\n", encoding="utf-8")
    assert gate.check_tests(test_dirs=(tests,), root=tmp_path) == 2


def test_test_runners_must_not_inject_the_flag(tmp_path: Path) -> None:
    gate = load_gate()
    makefile = tmp_path / "Makefile"
    makefile.write_text("# WB_ALLOW_LIVE_NETWORK stays in compose\ntest:\n\tnpm --workspace @proxima/collector test\n", encoding="utf-8")
    gate.check_test_runners(runners=(makefile,))
    makefile.write_text("test:\n\tWB_ALLOW_LIVE_NETWORK=1 npm --workspace @proxima/collector test\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="Makefile:2: WB_ALLOW_LIVE_NETWORK must not be set by a test/verify runner"):
        gate.check_test_runners(runners=(makefile,))


def test_transport_must_keep_the_fail_closed_seam(tmp_path: Path) -> None:
    gate = load_gate()
    original = (ROOT / "services" / "collector" / "src" / "wb" / "transport.ts").read_text(encoding="utf-8")
    opened = tmp_path / "transport.ts"
    opened.write_text(original.replace("if (process.env['WB_ALLOW_LIVE_NETWORK'] !== '1') {", "if (false) {"), encoding="utf-8")
    with pytest.raises(AssertionError, match="must stay fail-closed"):
        gate.check_transport(transport=opened)

    reordered = tmp_path / "reordered.ts"
    reordered.write_text(
        original.replace("    const { fetchTransport } = await import('../business-signal/http.js');\n", "").replace(
            "  return async (request) => {\n", "  return async (request) => {\n    const { fetchTransport } = await import('../business-signal/http.js');\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="before the real fetch transport"):
        gate.check_transport(transport=reordered)
