BEGIN;

CREATE ROLE proxima_loop_context NOLOGIN;
GRANT USAGE ON SCHEMA webapp_auth TO proxima_loop_context;
GRANT SELECT (id, name) ON webapp_auth."user" TO proxima_loop_context;
GRANT SELECT ON tenants TO proxima_loop_context;
GRANT SELECT ON collector_runs TO proxima_loop_context;
GRANT SELECT ON fact_cabinet_daily TO proxima_loop_context;
GRANT SELECT ON fact_cabinet_daily_current TO proxima_loop_context;
GRANT SELECT ON data_status_current TO proxima_loop_context;
GRANT SELECT ON brief_daily TO proxima_loop_context;
GRANT SELECT ON brief_current TO proxima_loop_context;
GRANT SELECT ON loop_tasks TO proxima_loop_context;
GRANT SELECT ON decision_records TO proxima_loop_context;
GRANT SELECT ON task_events TO proxima_loop_context;
GRANT SELECT ON cabinet_memberships TO proxima_loop_context;
CREATE POLICY tenant_isolation_loop_context ON collector_runs FOR SELECT TO proxima_loop_context USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_loop_context ON fact_cabinet_daily FOR SELECT TO proxima_loop_context USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_loop_context ON brief_daily FOR SELECT TO proxima_loop_context USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_loop_context ON loop_tasks FOR SELECT TO proxima_loop_context USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_loop_context ON decision_records FOR SELECT TO proxima_loop_context USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_loop_context ON task_events FOR SELECT TO proxima_loop_context USING (tenant_id = current_setting('proxima.tenant_id', true));
CREATE POLICY tenant_isolation_loop_context ON cabinet_memberships FOR SELECT TO proxima_loop_context USING (tenant_id = current_setting('proxima.tenant_id', true));

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (21, 'loop_context', '09830a86a438b539e4ed51f3806c88d2ec30d88da8eb3b72b3859728490f91e0');
COMMIT;
