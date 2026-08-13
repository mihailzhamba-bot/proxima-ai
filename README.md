# PROXIMA AI

Private read-only data foundation for one WB pilot. M1 keeps official WB evidence immutable, publishes operational, inventory and financial domains independently, and exposes provenance through a private Data Health control-plane.

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

The chosen host is Selectel Cloud in Russia: Ubuntu 24.04 LTS, 2 vCPU, 4 GiB RAM and 80 GiB NVMe, with a 3,000 RUB monthly budget cap. The machine has only TCP/22 inbound; any future private UI is reached through an SSH tunnel.

Before bootstrap, create the Selectel security group with only TCP/22 inbound and prepare one public SSH key for `proxima-admin`. From a clean temporary checkout of this private repository on the fresh host, run `sudo PROXIMA_SECURITY_GROUP_VERIFIED=yes PROXIMA_ADMIN_PUBLIC_KEY_FILE=/path/to/public-key bash infra/bootstrap/bootstrap-vps.sh`. It copies that exact clean checkout into `/srv/proxima-ai/repo`, so later operation does not depend on agent forwarding or a server-side GitHub credential.

The bootstrap does not start the host monitor. Create the Telegram secret files outside Git, test delivery into the private chat, and only then enable `proxima-host-monitor.timer`. It sends sanitized capacity alerts and makes no resize or other paid change automatically. Business data remains blocked until the backup guardrail is ready; complete recovery is still Phase 7.

For the one-off Day 1 API proof, run `sudo bash infra/bootstrap/prepare-day1-runtime.sh` after bootstrap. It creates an ignored path-only `.env`, generates PostgreSQL credentials under `/etc/proxima-ai/secrets`, installs the pinned `httpx` probe environment and starts the private PostgreSQL container. Install one read-only personal token with the `Статистика`, `Аналитика`, `Финансы`, `Цены и скидки` and `Продвижение` categories at `/etc/proxima-ai/secrets/wb_statistics_token`, owned by `proxima-admin` with mode `0600`; never put the token value in `.env`, shell history or Git. Then run `sudo -u proxima-admin /srv/proxima-ai/wb-probe-venv/bin/python tools/wb_api_probe.py --env-file .env`. The command prints the real seven-day sales JSON and a safe receipt; exact responses are content-addressed outside Git under `/srv/proxima-ai/data/day1-wb-api`.

Official WB intake, normalized facts, live scheduling, Data Health and the production Compose stack are implemented only in their owning roadmap phases. Torgstat live browser/session automation is not part of M1 and has no production entrypoint.
