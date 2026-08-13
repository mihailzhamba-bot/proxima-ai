.PHONY: verify install typecheck test contracts migrations provenance architecture boundary secrets vps probe-wb-api collect-wb-analytics apply-migrations

verify: install typecheck test contracts migrations provenance architecture boundary secrets vps

install:
	npm ci
	uv sync --python 3.14 --project services/control-plane --extra test --locked

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

probe-wb-api:
	uv run --python 3.14 --project services/control-plane --extra test python tools/wb_api_probe.py --env-file .env

apply-migrations:
	uv run --python 3.14 --project services/control-plane --extra test python tools/apply_migrations.py --env-file .env

collect-wb-analytics:
	uv run --python 3.14 --project services/control-plane --extra test python tools/wb_async_report.py --env-file .env --tenant-id amirova-test --period latest-closed-week
