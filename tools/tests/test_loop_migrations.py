import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location("loop_migration_verifier",Path(__file__).resolve().parents[1]/"verify_migrations.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
@pytest.mark.parametrize("grant",["GRANT DELETE ON loop_tasks TO proxima_loop_writer", "GRANT SELECT, INSERT, UPDATE, DELETE ON webapp_auth.auth_user TO proxima_loop_writer", "GRANT USAGE ON SCHEMA public TO proxima_auth_writer", 'GRANT SELECT, INSERT, UPDATE, DELETE ON webapp_auth."other" TO proxima_auth_writer'])
def test_auth_grant_exception_does_not_weaken_domain_matrix(grant):
    with pytest.raises(ValueError):mod.assert_additive_only("BEGIN; "+grant+"; COMMIT;","fixture.sql")
def test_existing_betterauth_table_identity_is_allowlisted():
    mod.assert_additive_only('BEGIN; GRANT SELECT, INSERT, UPDATE, DELETE ON webapp_auth."session" TO proxima_auth_writer; COMMIT;',"fixture.sql")
