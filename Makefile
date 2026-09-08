.PHONY: agent-toolset apply-migrations architecture boundary brief business-signal codegen codegen-diff collect-wb-analytics contracts detector funnel funnel-csv hooks install migrations nm-daily pg-roundtrip probe-wb-api provenance secrets test test-db-refresh typecheck verify vps wb-async-report wb-client webapp-build webapp-lint


verify: install codegen codegen-diff typecheck webapp-lint test contracts migrations pg-roundtrip provenance architecture boundary secrets vps business-signal wb-client brief wb-async-report funnel funnel-csv nm-daily detector

install: hooks
	npm ci
	uv sync --python 3.14 --project services/control-plane --extra test --locked

hooks:
	@if git rev-parse --git-dir >/dev/null 2>&1; then git config --local core.hooksPath .githooks; echo "hooks: core.hooksPath=.githooks"; else echo "hooks: SKIP (not a git repository)"; fi

codegen:
	npm run codegen:contracts

codegen-diff: codegen
	@git diff --exit-code --stat -- services/collector/src/contracts services/webapp/src/lib/contracts || { echo "codegen-diff: FAIL: generated contract files differ from HEAD; run 'make codegen' and commit the results" >&2; exit 1; }
	@untracked="$$(git ls-files --others --exclude-standard -- services/collector/src/contracts services/webapp/src/lib/contracts)"; \
	if [ -n "$$untracked" ]; then printf '%s\n' "$$untracked"; echo "codegen-diff: FAIL: untracked generated contract files found; run 'make codegen' and commit the results" >&2; exit 1; fi
	@echo "codegen-diff: PASS"

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

# Story 3.2: wb_async_report.py as a funnel_csv_download ledger run (contract gate, stdlib only).
wb-async-report:
	uv run --python 3.14 python tools/verify_wb_async_report.py

funnel:
	uv run --python 3.14 python tools/verify_funnel.py

# Story 3.3: durable CSV rows promote into shared funnel facts and replay after deletion.
funnel-csv:
	uv run --python 3.14 python tools/verify_funnel_csv.py

# Story 4.0 (AD-19): `order-counts: per-nm sums vs cabinet` - the node:test on the fixtures plus the 018/writer pins.
nm-daily:
	uv run --python 3.14 python tools/verify_nm_daily.py

detector:
	uv run --python 3.14 --project services/control-plane --extra test python tools/verify_detector.py
