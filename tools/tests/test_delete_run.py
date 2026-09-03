"""Offline unit tests for tools/delete_run.py (Story 1.7).

No network, no database: closure math, contract validation and the
refusal wording of AD-3 ("0 строк для run_id") are exercised directly.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_tool() -> object:
    spec = importlib.util.spec_from_file_location("delete_run", ROOT / "tools" / "delete_run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["delete_run"] = module
    spec.loader.exec_module(module)
    return module


delete_run = load_tool()

RUN = uuid.UUID("11111111-1111-1111-1111-111111111111")
COLLECT = uuid.UUID("22222222-2222-2222-2222-222222222222")
SECOND_INPUT = uuid.UUID("33333333-3333-3333-3333-333333333333")
DEPENDENT = uuid.UUID("44444444-4444-4444-4444-444444444444")
GRANDCHILD = uuid.UUID("55555555-5555-5555-5555-555555555555")
UNRELATED = uuid.UUID("66666666-6666-6666-6666-666666666666")


def test_missing_tenant_argument_reaches_the_zero_rows_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """AC: without --tenant the error is "0 строк для run_id" - the GUC is
    never set and RLS hides the run - never zeros and never a usage error."""

    class GuclessConnection:
        def execute(self, query: str, params: tuple[object, ...] | None = None) -> "GuclessConnection":
            self.query = query
            return self

        def close(self) -> None:
            return None

        def fetchone(self) -> tuple[int]:
            if "FROM collector_runs" in self.query:
                return (0,)
            raise AssertionError(f"unexpected query after the guard: {self.query}")

    monkeypatch.setattr(delete_run.psycopg, "connect", lambda *args, **kwargs: GuclessConnection())
    monkeypatch.setenv("JANITOR_DATABASE_URI", "postgresql://janitor@h/db")
    assert delete_run.main(["--run", str(RUN)]) == 1
    err = capsys.readouterr().err
    assert "0 строк для run_id" in err
    assert str(RUN) not in err
    assert "delete_run: deleted" not in err


def test_invalid_tenant_format_refuses(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("JANITOR_DATABASE_URI_FILE", raising=False)
    monkeypatch.delenv("JANITOR_DATABASE_URI", raising=False)
    assert delete_run.main(["--tenant", "Not A Tenant", "--run", str(RUN)]) == 1
    assert "valid tenant ID" in capsys.readouterr().err


def test_invalid_run_uuid_refuses() -> None:
    with pytest.raises(delete_run.DeleteRunError, match="must be a UUID"):
        delete_run.parse_run_id("not-a-uuid")


def test_missing_uri_configuration_refuses_with_the_wording_of_the_convention(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JANITOR_DATABASE_URI_FILE", raising=False)
    monkeypatch.delenv("JANITOR_DATABASE_URI", raising=False)
    assert delete_run.main(["--tenant", "amirova-test", "--run", str(RUN)]) == 1
    err = capsys.readouterr().err
    assert "JANITOR_DATABASE_URI_FILE" in err


def test_uri_file_symlink_and_group_readable_refuse(tmp_path: Path) -> None:
    target = tmp_path / "real.uri"
    target.write_text("postgresql://u:p@h/db\n")
    target.chmod(0o600)
    link = tmp_path / "link.uri"
    link.symlink_to(target)
    with pytest.raises(delete_run.DeleteRunError, match="regular file"):
        delete_run.read_uri_file(link)
    loose = tmp_path / "loose.uri"
    loose.write_text("postgresql://u:p@h/db\n")
    loose.chmod(0o644)
    with pytest.raises(delete_run.DeleteRunError, match="unsafe permissions"):
        delete_run.read_uri_file(loose)
    assert stat.S_IMODE(loose.stat().st_mode) & 0o077


def test_uri_file_with_two_lines_refuses(tmp_path: Path) -> None:
    two = tmp_path / "two.uri"
    two.write_text("line-one\nline-two\n")
    two.chmod(0o600)
    with pytest.raises(delete_run.DeleteRunError, match="exactly one non-empty value"):
        delete_run.read_uri_file(two)


def test_janitor_dsn_prefers_the_file_over_the_bare_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    uri_file = tmp_path / "janitor_uri"
    uri_file.write_text("postgresql://from-file@h/db\n")
    uri_file.chmod(0o600)
    monkeypatch.setenv("JANITOR_DATABASE_URI_FILE", str(uri_file))
    monkeypatch.setenv("JANITOR_DATABASE_URI", "postgresql://from-env@h/db")
    assert delete_run.janitor_dsn() == "postgresql://from-file@h/db"
    monkeypatch.delenv("JANITOR_DATABASE_URI_FILE")
    assert delete_run.janitor_dsn() == "postgresql://from-env@h/db"


def test_closure_walks_inputs_up_and_dependants_down() -> None:
    """AD-3: deleting a backfill = closure onto all its collects (the
    documented full walk); and nothing consuming a deleted run survives."""
    inputs = {
        # a backfill consumed two collects
        DEPENDENT: [COLLECT, SECOND_INPUT],
        # a norm consumed that backfill
        GRANDCHILD: [DEPENDENT],
    }
    # deleting the backfill takes its two collects (upward walk) and the norm
    # that consumed it (downward elimination)
    assert set(delete_run.closure_run_ids(inputs, DEPENDENT)) == {DEPENDENT, COLLECT, SECOND_INPUT, GRANDCHILD}
    # deleting one collect takes the backfill that consumed it and the norm
    # above it; the sibling collect SECOND_INPUT survives - it is intact
    # evidence, and the RESTRICT on input_run_id is what the eliminator
    # prevents from ever being hit
    assert set(delete_run.closure_run_ids(inputs, COLLECT)) == {COLLECT, DEPENDENT, GRANDCHILD}
    # deleting a leaf takes the whole closure: its inputs upward (AD-3's
    # "deleting a backfill = closure onto all collects" example generalizes)
    # plus every consumer downward
    assert set(delete_run.closure_run_ids(inputs, GRANDCHILD)) == {GRANDCHILD, DEPENDENT, COLLECT, SECOND_INPUT}
    assert delete_run.closure_run_ids({}, RUN) == [RUN]
    assert UNRELATED not in delete_run.closure_run_ids(inputs, COLLECT)


def test_closure_cycles_terminate() -> None:
    inputs = {DEPENDENT: [COLLECT], COLLECT: [DEPENDENT]}
    closure = delete_run.closure_run_ids(inputs, DEPENDENT)
    assert set(closure) == {DEPENDENT, COLLECT}


def test_zero_rows_wording_is_the_contract_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """With a wrong or foreign run UUID the janitor sees zero rows: the tool
    must fail loudly with "0 строк для run_id", never delete zero rows and
    report success."""

    class FakeConnection:
        def execute(self, query: str, params: tuple[object, ...] | None = None) -> "FakeConnection":
            self.query = query
            self.params = params
            return self

        def close(self) -> None:
            return None

        def fetchone(self) -> tuple[int]:
            if "FROM collector_runs" in self.query:
                return (0,)
            raise AssertionError(f"unexpected query after the guard: {self.query}")

    monkeypatch.setattr(delete_run.psycopg, "connect", lambda *args, **kwargs: FakeConnection())
    monkeypatch.setenv("JANITOR_DATABASE_URI", "postgresql://janitor@h/db")
    assert delete_run.main(["--tenant", "amirova-test", "--run", str(RUN)]) == 1
    err = capsys.readouterr().err
    assert "0 строк для run_id" in err
    assert str(RUN) in err
    assert "delete_run: deleted" not in err
