# PROJECT — PROXIMA AI

- What: private WB data platform for Proxima agency cabinets. M1 = production-ready read-only data foundation of one pilot cabinet (Bogatova Belle Robe): official WB intent → immutable SHA-256 artifacts → PostgreSQL normalization → atomic domain releases.
- Product layers M2 (AI Daily Manager), M3 (SaaS): `docs/archive/planning-m1/PRODUCT-VISION.md`.
- Owner: Mike (Proxima). Tracker: Jira project PA (epics PA-36 Track A, PA-37 Track B, PA-35 Track C, PA-34 Track D frozen).
- Stack: Node 22 + TypeScript (collector), Python 3.14 via uv (control-plane), PostgreSQL 16 (VPS, SSH tunnel — no local Docker).
- Source: root AGENTS.md (full contract), `docs/archive/planning-m1/ROADMAP.md`, updated 2026-08-16.
