.PHONY: agent-toolset apply-migrations architecture boundary business-signal codegen collect-wb-analytics contracts install migrations probe-wb-api provenance secrets test typecheck verify vps


verify: install codegen typecheck test contracts migrations provenance architecture boundary secrets vps business-signal

install:
	npm ci
	uv sync --python 3.14 --project services/control-plane --extra test --locked

codegen:
	npm run codegen:contracts

typecheck:
	npm --workspace @proxima/collector run typecheck

test:
	npm --workspace @proxima/collector test
	uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests tools/tests

contracts:
	uv run --python 3.14 --project services/control-plane --extra test python tools/verify_contracts.py

migrations:
	uv run --python 3.14 python tools/verify_migrations.py

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

apply-migrations:
	uv run --python 3.14 --project services/control-plane --extra test python tools/apply_migrations.py --env-file .env

collect-wb-analytics:
	uv run --python 3.14 --project services/control-plane --extra test python tools/wb_async_report.py --env-file .env --tenant-id amirova-test --period latest-closed-week
