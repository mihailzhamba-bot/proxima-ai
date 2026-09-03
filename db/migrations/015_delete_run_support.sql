BEGIN;

-- Story 1.7 (AD-3/AD-11): the janitor reads the ledger to compute the
-- transitive closure before deleting; the DELETE grant itself stays outside
-- the ledger (bootstrap provision-runtime-roles.sh).
GRANT SELECT ON collector_runs TO proxima_run_janitor;
GRANT SELECT ON collector_run_inputs TO proxima_run_janitor;
GRANT SELECT ON wb_raw_artifacts TO proxima_run_janitor;

-- AD-11: FOR ALL on everything carrying run_id. business_signal_runs predates
-- the ledger (004) and was never given its janitor policy; its runtime role is
-- the table owner and bypasses RLS, so the policy only governs the janitor.
ALTER TABLE business_signal_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_janitor ON business_signal_runs FOR ALL TO proxima_run_janitor USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (15, 'delete_run_support', '52af2ee11403f2d61c1c082b764ae4fc459670f30cc2aaa7263113a1993ef8ba');
COMMIT;
