.PHONY: verify setup install start dev _runtime-check typecheck test contracts migrations provenance architecture boundary secrets vps business-signal probe-wb-api collect-wb-analytics apply-migrations

NPM ?= npm
TSX ?= ./node_modules/.bin/tsx

verify: install typecheck test contracts migrations provenance architecture boundary secrets vps business-signal

setup:
	$(NPM) ci
	uv sync --python 3.14 --project services/control-plane --extra test --locked

install: setup

_runtime-check:
	@set -eu; \
	require_value() { \
		if [ -z "$$2" ]; then \
			printf '%s\n' "runtime-check: $$1 is required" >&2; \
			exit 2; \
		fi; \
	}; \
	require_file() { \
		if [ ! -f "$$2" ] || [ ! -r "$$2" ]; then \
			printf '%s\n' "runtime-check: $$1 must point to a readable regular file" >&2; \
			exit 2; \
		fi; \
	}; \
	require_value PROXIMA_TENANT_ID "$${PROXIMA_TENANT_ID:-}"; \
	require_value PROXIMA_DATABASE_URL_FILE "$${PROXIMA_DATABASE_URL_FILE:-}"; \
	require_value PROXIMA_SIGNAL_RAW_DIR "$${PROXIMA_SIGNAL_RAW_DIR:-}"; \
	require_value WB_STATISTICS_TOKEN_FILE "$${WB_STATISTICS_TOKEN_FILE:-}"; \
	require_value WB_ANALYTICS_TOKEN_FILE "$${WB_ANALYTICS_TOKEN_FILE:-}"; \
	require_value WB_FINANCE_TOKEN_FILE "$${WB_FINANCE_TOKEN_FILE:-}"; \
	case "$${PROXIMA_ALLOW_ANALYTICS_READ_WRITE:-0}" in \
		0|1) ;; \
		*) printf '%s\n' 'runtime-check: PROXIMA_ALLOW_ANALYTICS_READ_WRITE must be 0 or 1' >&2; exit 2 ;; \
	esac; \
	if [ ! -x "$(TSX)" ]; then \
		printf '%s\n' 'runtime-check: Node dependencies are missing; run make setup' >&2; \
		exit 2; \
	fi; \
	require_file PROXIMA_DATABASE_URL_FILE "$$PROXIMA_DATABASE_URL_FILE"; \
	require_file WB_STATISTICS_TOKEN_FILE "$$WB_STATISTICS_TOKEN_FILE"; \
	require_file WB_ANALYTICS_TOKEN_FILE "$$WB_ANALYTICS_TOKEN_FILE"; \
	require_file WB_FINANCE_TOKEN_FILE "$$WB_FINANCE_TOKEN_FILE"

start: _runtime-check
	$(NPM) run build
	@set -eu; \
	set -- \
		--tenant "$$PROXIMA_TENANT_ID" \
		--database-url-file "$$PROXIMA_DATABASE_URL_FILE" \
		--raw-root "$$PROXIMA_SIGNAL_RAW_DIR" \
		--statistics-token-file "$$WB_STATISTICS_TOKEN_FILE" \
		--analytics-token-file "$$WB_ANALYTICS_TOKEN_FILE" \
		--finance-token-file "$$WB_FINANCE_TOKEN_FILE"; \
	if [ "$${PROXIMA_ALLOW_ANALYTICS_READ_WRITE:-0}" = 1 ]; then \
		set -- "$$@" --allow-analytics-read-write; \
	fi; \
	exec $(NPM) --silent --workspace @proxima/collector run stockout-signal -- "$$@"

dev: _runtime-check
	@set -eu; \
	set -- \
		--tenant "$$PROXIMA_TENANT_ID" \
		--database-url-file "$$PROXIMA_DATABASE_URL_FILE" \
		--raw-root "$$PROXIMA_SIGNAL_RAW_DIR" \
		--statistics-token-file "$$WB_STATISTICS_TOKEN_FILE" \
		--analytics-token-file "$$WB_ANALYTICS_TOKEN_FILE" \
		--finance-token-file "$$WB_FINANCE_TOKEN_FILE"; \
	if [ "$${PROXIMA_ALLOW_ANALYTICS_READ_WRITE:-0}" = 1 ]; then \
		set -- "$$@" --allow-analytics-read-write; \
	fi; \
	exec $(TSX) services/collector/src/cli/stockout-signal.ts "$$@"

typecheck:
	$(NPM) --workspace @proxima/collector run typecheck

test:
	$(NPM) --workspace @proxima/collector test
	uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests tools/tests

contracts:
	uv run --python 3.14 --project services/control-plane --extra test python tools/verify_contracts.py

migrations:
	uv run --python 3.14 python tools/verify_migrations.py

provenance:
	uv run --python 3.14 python tools/verify_provenance.py

architecture:
	$(NPM) run architecture:render

boundary:
	uv run --python 3.14 python tools/verify_runtime_boundary.py

secrets:
	uv run --python 3.14 python tools/secret_scan.py --self-test
	uv run --python 3.14 python tools/secret_scan.py

vps:
	uv run --python 3.14 python tools/verify_vps_contract.py

business-signal:
	uv run --python 3.14 python tools/verify_business_signal.py

probe-wb-api:
	uv run --python 3.14 --project services/control-plane --extra test python tools/wb_api_probe.py --env-file .env

apply-migrations:
	uv run --python 3.14 --project services/control-plane --extra test python tools/apply_migrations.py --env-file .env

collect-wb-analytics:
	uv run --python 3.14 --project services/control-plane --extra test python tools/wb_async_report.py --env-file .env --tenant-id amirova-test --period latest-closed-week
