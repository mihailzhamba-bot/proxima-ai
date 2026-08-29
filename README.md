# PROXIMA AI

Private read-only data foundation for one WB pilot. M1 keeps official WB evidence immutable, publishes operational, inventory and financial domains independently, and exposes provenance through a private Data Health control-plane.

## Project commands

Use the root Makefile as the project entrypoint. The local toolchain requires Node 22.x, Python 3.14, npm, uv and GNU Make.

| Command | Purpose | Requirements |
| --- | --- | --- |
| `make setup` | Install locked Node and Python dependencies with `npm ci` and `uv sync` | Node 22.x, Python 3.14, npm and uv |
| `make start` | Build and run the compiled business-signal collector once without Telegram delivery | `make setup` and the runtime variables below |
| `make dev` | Run the same one-shot collector directly from TypeScript through the locked local `tsx` | `make setup` and the runtime variables below |
| `make test` | Run the Node and Python test suites | Installed dependencies |
| `make verify` | Run the complete local and CI contract | Installed toolchain; dependencies are refreshed automatically |

`make install` remains a compatibility alias for `make setup`. The other focused verification targets, including `contracts`, `migrations`, `architecture`, `secrets`, `vps` and `business-signal`, remain available.

Export path-only runtime configuration before `make start` or `make dev`:

```bash
export PROXIMA_TENANT_ID=amirova-test
export PROXIMA_DATABASE_URL_FILE=/absolute/private/postgres_url
export PROXIMA_SIGNAL_RAW_DIR=/absolute/private/business-signal-raw
export WB_STATISTICS_TOKEN_FILE=/absolute/private/wb_statistics_token
export WB_ANALYTICS_TOKEN_FILE=/absolute/private/wb_analytics_token
export WB_FINANCE_TOKEN_FILE=/absolute/private/wb_finance_token
```

The database URL and WB token files must be private regular files with mode `0600`. The raw directory must be outside the Git checkout; the collector creates it with private permissions when needed. If the staging Analytics token is still read-write, explicitly export `PROXIMA_ALLOW_ANALYTICS_READ_WRITE=1`; the default is read-only enforcement.

Both runtime targets are one-shot dry runs of the implemented `stockout-signal` path. They never add `--send`, read Telegram credentials or start the deferred control-plane and scheduler. Preflight errors identify the missing variable or unreadable file without printing a secret value or secret path.

## Architecture

- Visual entrypoint: `docs/architecture/system.mmd`
- Data path: `docs/architecture/data-flow.mmd`
- One-VPS boundary: `docs/architecture/deployment.mmd`
- Delivery and review loop: `docs/architecture/delivery.mmd`

Render all maps with `make architecture`. Run the complete local contract with `make verify`.

## Implemented now

- TypeScript collector/data-plane package with provenance-bound safety primitives.
- Python 3.14 control-plane package boundary.
- PostgreSQL 16 private Compose skeleton and self-recording bootstrap migration.
- Cross-language artifact, attempt and domain-release contracts.
- Reproducible Selectel staging-VPS bootstrap: SSH hardening, private Docker host, capacity-monitor contract and a disabled-by-default systemd timer.

## Staging VPS

The approved host is Selectel Cloud in Russia at `135.106.186.210`: Ubuntu 24.04 LTS, 6 vCPU, a 12 GiB RAM class and a 120 GiB NVMe class. These dimensions were observed by SSH preflight on 2026-08-13 and retained by Mike the same day. The 3,000 RUB monthly budget cap remains, but the actual Selectel monthly price is not yet verified. The machine has only TCP/22 inbound; any future private UI is reached through an SSH tunnel.

Before bootstrap, create the Selectel security group with only TCP/22 inbound and prepare one public SSH key for `proxima-admin`. From a clean temporary checkout of this private repository on the fresh host, run `sudo PROXIMA_SECURITY_GROUP_VERIFIED=yes PROXIMA_ADMIN_PUBLIC_KEY_FILE=/path/to/public-key bash infra/bootstrap/bootstrap-vps.sh`. It copies that exact clean checkout into `/srv/proxima-ai/repo`, so later operation does not depend on agent forwarding or a server-side GitHub credential.

The bootstrap does not start the host monitor. Create the Telegram secret files outside Git, test delivery into the private chat, and only then enable `proxima-host-monitor.timer`. It sends sanitized capacity alerts and makes no resize or other paid change automatically. Business data remains blocked until the backup guardrail is ready; complete recovery is still Phase 7.

For the one-off Day 1 API proof, run `sudo bash infra/bootstrap/prepare-day1-runtime.sh` after bootstrap. It creates an ignored path-only `.env`, generates PostgreSQL credentials under `/etc/proxima-ai/secrets`, installs the pinned `httpx` probe environment and starts the private PostgreSQL container. Install five split read-only personal tokens, one per category, at `/etc/proxima-ai/secrets/wb_statistics_token`, `wb_analytics_token`, `wb_finance_token`, `wb_prices_token` and `wb_promotion_token`, each granting only its category (`Статистика`, `Аналитика`, `Финансы`, `Цены и скидки`, `Продвижение`), owned by `proxima-admin` with mode `0600`; never put a token value in `.env`, shell history or Git. While the staging Analytics token remains read-write, pass the documented `--allow-analytics-read-write` flag. Then run `sudo -u proxima-admin /srv/proxima-ai/wb-probe-venv/bin/python tools/wb_api_probe.py --env-file .env`. The command prints the real seven-day sales JSON and a safe receipt covering ping checks of all five WB API domains; exact responses are content-addressed outside Git under `/srv/proxima-ai/data/day1-wb-api`.

The async Analytics CSV proof uses the same prepared runtime. Install the test cabinet's read-only personal Analytics token at `/etc/proxima-ai/secrets/wb_analytics_token`, owned by `proxima-admin` with mode `0600`. From `/srv/proxima-ai/repo`, run `sudo -u proxima-admin /srv/proxima-ai/wb-probe-venv/bin/python tools/wb_async_report.py --env-file .env --tenant-id amirova-test --period latest-closed-week`. The collector reserves its client-generated UUID and daily quota slot in PostgreSQL before any create request, resumes that UUID after failure, treats `WAITING`, `PROCESSING` and `RETRY` as wait states, and stores every exact response as base64-backed JSONB before inspection. Its stdout contains only task metadata, SHA-256 and byte size; it never prints the raw report.

Official WB intake, normalized facts, live scheduling, Data Health and the production Compose stack are implemented only in their owning roadmap phases. Torgstat live browser/session automation is not part of M1 and has no production entrypoint.
