BEGIN;
CREATE TABLE dim_client_passport (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    effective_from date NOT NULL,
    sales_drop_threshold_pct numeric(5,2) NOT NULL CHECK (sales_drop_threshold_pct > 0 AND sales_drop_threshold_pct <= 100),
    days_cover_threshold_days integer NOT NULL CHECK (days_cover_threshold_days >= 1),
    lead_time_days integer NOT NULL CHECK (lead_time_days >= 1),
    safety_buffer_days integer NOT NULL CHECK (safety_buffer_days >= 0),
    cogs_status text NOT NULL CHECK (cogs_status IN ('complete', 'top_sku', 'missing')),
    priority_categories jsonb NOT NULL DEFAULT '[]'::jsonb,
    warehouses jsonb NOT NULL DEFAULT '[]'::jsonb,
    weekend_days jsonb NOT NULL DEFAULT '[]'::jsonb,
    contacts jsonb NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (tenant_id, effective_from)
);
CREATE TABLE stg_supply_plan (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    supply_id text NOT NULL,
    nm_id bigint NOT NULL CHECK (nm_id > 0),
    quantity integer NOT NULL CHECK (quantity >= 1),
    order_date date NOT NULL,
    expected_arrival_date date NOT NULL,
    status text NOT NULL CHECK (status IN ('PLAN', 'SHIPPED', 'ACCEPTED', 'CANCELLED')),
    entered_by text NOT NULL,
    entered_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, supply_id)
);
-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (7, 'client_passport_supply_plan', '6aca0dbe3d0df0bd47d40795cee618dd3ae354d0532fca3eefdc32ed08c09c34');
COMMIT;
