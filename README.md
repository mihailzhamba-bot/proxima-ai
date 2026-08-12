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

Official WB intake, normalized facts, live scheduling, Data Health and deployment are implemented only in their owning roadmap phases. Torgstat live browser/session automation is not part of M1 and has no production entrypoint.
