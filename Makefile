.PHONY: agent-toolset apply-migrations architecture boundary brief business-signal codegen collect-wb-analytics contracts install migrations pg-roundtrip probe-wb-api provenance secrets test test-db-refresh typecheck verify vps wb-client webapp-build webapp-lint


verify: install codegen typecheck test contracts migrations pg-roundtrip provenance architecture boundary secrets vps business-signal wb-client brief

install:
	npm ci
	uv sync --python 3.14 --project services/control-plane --extra test --locked

codegen:
	npm run codegen:contracts

typecheck:
	npm --workspace @proxima/collector run typecheck
	npm --workspace @proxima/webapp run typecheck

test:
	npm --workspace @proxima/collector test
	npm --workspace @proxima/webapp test
	uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests tools/tests

webapp-lint:
	npm --workspace @proxima/webapp run lint

webapp-build:
	npm --workspace @proxima/webapp run build

contracts:
	uv run --python 3.14 --project services/control-plane --extra test python tools/verify_contracts.py

migrations:
	uv run --python 3.14 python tools/verify_migrations.py

pg-roundtrip:
	bash tools/pg_local_roundtrip.sh

test-db-refresh:
	bash tools/test_db_refresh.sh

provenance:
	uv run --python 3.14 python tools/verify_provenance.py

architecture:
	npm run architecture:render

boundary:
	uv run --python 3.14 python tools/verify_runtime_boundary.py

secrets:
	uv run --python 3.14 python tools/secret_scan.py --self-test
	uv run --python 3.14 python tools/secret_scan.py

vps:
	uv run --python 3.14 python tools/verify_vps_contract.py

business-signal:
	uv run --python 3.14 python tools/verify_business_signal.py

agent-toolset:
	uv run --python 3.14 python tools/verify_agent_toolset.py

probe-wb-api:
	uv run --python 3.14 --project services/control-plane --extra test python tools/wb_api_probe.py --env-file .env

# Owner-URI env file: repository root .env on the host (AD-15), infra/jobs.env inside control-plane-admin.
ENV_FILE ?= .env

apply-migrations:
	uv run --python 3.14 --project services/control-plane --extra test python tools/apply_migrations.py --env-file $(ENV_FILE)

collect-wb-analytics:
	uv run --python 3.14 --project services/control-plane --extra test python tools/wb_async_report.py --env-file .env --tenant-id amirova-test --period latest-closed-week

wb-client:
	uv run --python 3.14 python tools/verify_wb_client.py

brief:
	uv run --python 3.14 --project services/control-plane --extra test python tools/verify_brief.py
