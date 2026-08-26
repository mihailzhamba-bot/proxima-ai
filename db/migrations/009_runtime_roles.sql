BEGIN;

CREATE ROLE proxima_migration_owner NOLOGIN;
CREATE ROLE proxima_source_publisher NOLOGIN;
CREATE ROLE proxima_release_publisher NOLOGIN;
CREATE ROLE proxima_data_health_read NOLOGIN;

GRANT SELECT, INSERT, UPDATE ON schema_migrations TO proxima_migration_owner;

GRANT SELECT, INSERT ON fact_attempt_runs TO proxima_source_publisher;
GRANT SELECT, INSERT ON stg_quarantine_rows TO proxima_source_publisher;
GRANT SELECT, INSERT ON fact_order_counts TO proxima_source_publisher;
GRANT SELECT, INSERT ON fact_lineage_records TO proxima_source_publisher;
GRANT SELECT, INSERT ON quality_check_results TO proxima_source_publisher;
GRANT SELECT ON stg_wb_nm_report_rows TO proxima_source_publisher;
GRANT SELECT ON wb_analytics_report_tasks TO proxima_source_publisher;
GRANT SELECT ON raw_wb_analytics_responses TO proxima_source_publisher;
GRANT SELECT ON source_artifacts TO proxima_source_publisher;
GRANT SELECT ON artifact_manifests TO proxima_source_publisher;
GRANT SELECT ON intake_attempts TO proxima_source_publisher;
GRANT USAGE, SELECT ON SEQUENCE stg_quarantine_rows_quarantine_id_seq TO proxima_source_publisher;
GRANT USAGE, SELECT ON SEQUENCE fact_order_counts_fact_id_seq TO proxima_source_publisher;
GRANT USAGE, SELECT ON SEQUENCE fact_lineage_records_lineage_id_seq TO proxima_source_publisher;
GRANT USAGE, SELECT ON SEQUENCE quality_check_results_check_id_seq TO proxima_source_publisher;

GRANT SELECT ON fact_attempt_runs TO proxima_release_publisher;
GRANT SELECT ON fact_order_counts TO proxima_release_publisher;
GRANT SELECT ON fact_lineage_records TO proxima_release_publisher;
GRANT SELECT ON quality_check_results TO proxima_release_publisher;
GRANT SELECT, INSERT ON release_attempts TO proxima_release_publisher;
GRANT SELECT, INSERT ON release_promoted_facts TO proxima_release_publisher;
GRANT SELECT, UPDATE ON domain_release_pointers TO proxima_release_publisher;

GRANT SELECT ON fact_attempt_runs TO proxima_data_health_read;
GRANT SELECT ON stg_quarantine_rows TO proxima_data_health_read;
GRANT SELECT ON fact_order_counts TO proxima_data_health_read;
GRANT SELECT ON fact_lineage_records TO proxima_data_health_read;
GRANT SELECT ON quality_check_results TO proxima_data_health_read;
GRANT SELECT ON release_attempts TO proxima_data_health_read;
GRANT SELECT ON release_promoted_facts TO proxima_data_health_read;
GRANT SELECT ON domain_release_pointers TO proxima_data_health_read;
GRANT SELECT ON public_order_counts_operational TO proxima_data_health_read;
GRANT SELECT ON public_order_counts_inventory TO proxima_data_health_read;
GRANT SELECT ON public_order_counts_financial TO proxima_data_health_read;

ALTER TABLE fact_attempt_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE stg_quarantine_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_order_counts ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_lineage_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality_check_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE release_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE release_promoted_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE domain_release_pointers ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_source ON fact_attempt_runs
    FOR ALL TO proxima_source_publisher
    USING (tenant_id = current_setting('proxima.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_source ON stg_quarantine_rows
    FOR ALL TO proxima_source_publisher
    USING (tenant_id = current_setting('proxima.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_source ON fact_order_counts
    FOR ALL TO proxima_source_publisher
    USING (tenant_id = current_setting('proxima.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_source ON fact_lineage_records
    FOR ALL TO proxima_source_publisher
    USING (tenant_id = current_setting('proxima.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_source ON quality_check_results
    FOR ALL TO proxima_source_publisher
    USING (tenant_id = current_setting('proxima.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_release ON release_attempts
    FOR ALL TO proxima_release_publisher
    USING (tenant_id = current_setting('proxima.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_release ON release_promoted_facts
    FOR ALL TO proxima_release_publisher
    USING (tenant_id = current_setting('proxima.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_release ON domain_release_pointers
    FOR ALL TO proxima_release_publisher
    USING (tenant_id = current_setting('proxima.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_read ON fact_attempt_runs
    FOR SELECT TO proxima_data_health_read
    USING (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_read ON stg_quarantine_rows
    FOR SELECT TO proxima_data_health_read
    USING (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_read ON fact_order_counts
    FOR SELECT TO proxima_data_health_read
    USING (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_read ON fact_lineage_records
    FOR SELECT TO proxima_data_health_read
    USING (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_read ON quality_check_results
    FOR SELECT TO proxima_data_health_read
    USING (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_read ON release_attempts
    FOR SELECT TO proxima_data_health_read
    USING (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_read ON release_promoted_facts
    FOR SELECT TO proxima_data_health_read
    USING (tenant_id = current_setting('proxima.tenant_id', true));

CREATE POLICY tenant_isolation_read ON domain_release_pointers
    FOR SELECT TO proxima_data_health_read
    USING (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (9, 'runtime_roles', '2313786148d11fbbf69eca33a44b18fb906af2db213635325a9306d644dd1585');

COMMIT;
