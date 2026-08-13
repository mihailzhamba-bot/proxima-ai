---
phase: 02-vertical-slice-immutable-intake
plan: 01A
type: execute
requirements: []
depends_on: [02-01]
wave: 1a
autonomous: true
must_haves:
  truths:
    - "One manual run calculates one margin and selects one deterministic top out-of-stock risk."
    - "Every WB response is durable with SHA-256 provenance before parse; schema drift or incomplete pagination blocks Telegram."
    - "A send attempt produces at most one formatted Telegram message and never retries automatically."
  artifacts:
    - "db/migrations/004_business_signal_slice.sql"
    - "services/collector/src/business-signal/*"
    - "services/collector/src/cli/stockout-signal.ts"
    - "docs/operations/business-signal-runbook.md"
  key_links:
    - "three separate private WB token files -> official READ endpoints -> raw content store -> strict parse"
    - "dim_product plus warehouse mapping -> 14-day velocity and Decimal margin -> one top risk"
    - "private founder chat source -> getMe/getChat -> one sendMessage call site"
---

# Plan 02-01A - Margin and out-of-stock Telegram proof

## Objective

Give the founder one early staging feedback signal before continuing the Phase 2 XLSX parser: for a few privately configured SKU, calculate `price - commission - logistics - COGS`, estimate stock days at current 14-day net sales velocity, select one deterministic top risk, and optionally send one Telegram message.

This is a staging exception for `amirova-test`. It does not move a production release pointer, complete Phase 2 requirements, add a scheduler, or change Data GO / Live Deploy GO.

## Tasks

<tasks>

<task type="auto">
  <name>Task 1: Add versioned config and provenance schema</name>
  <files>db/migrations/004_business_signal_slice.sql, services/collector/src/business-signal/config.ts, services/collector/src/business-signal/types.ts, services/collector/tests/business-signal-config.test.ts</files>
  <action>Add versioned dim_product and warehouse mapping, one-shot run/raw lineage tables, and private strict CSV seed. Do not commit SKU, COGS, chat ID or secret values.</action>
  <verify><automated>uv run --python 3.14 python tools/verify_migrations.py &amp;&amp; npm --workspace @proxima/collector test</automated></verify>
</task>

<task type="auto">
  <name>Task 2: Collect, calculate and send one signal</name>
  <files>services/collector/src/business-signal/*, services/collector/src/cli/seed-signal-config.ts, services/collector/src/cli/stockout-signal.ts, services/collector/tests/business-signal.test.ts</files>
  <action>Use separate least-privilege Statistics, Analytics and Finance token files. Persist exact response bytes before strict parse. Block unknown schema/mapping/pagination. Calculate 14 completed Moscow days, select one risk and use one escaped Telegram send without automatic retry.</action>
  <verify><automated>npm --workspace @proxima/collector run typecheck &amp;&amp; npm --workspace @proxima/collector test</automated></verify>
</task>

<task type="auto">
  <name>Task 3: Add pinned VPS runtime and operator contract</name>
  <files>infra/bootstrap/prepare-business-signal-runtime.sh, docs/operations/business-signal-runbook.md, tools/verify_business_signal.py, tools/verify_vps_contract.py, Makefile</files>
  <action>Install and verify Node 22 on a host where Node/npm are absent, build the collector, document private setup/dry-run/one-send steps and keep scheduler/live mutation outside repository execution.</action>
  <verify><automated>bash -n infra/bootstrap/prepare-business-signal-runtime.sh &amp;&amp; make verify &amp;&amp; git diff --check</automated></verify>
</task>

</tasks>

## External acceptance checkpoint

Repository implementation is ready when all automated gates pass. End-to-end acceptance remains pending until root deploys the reviewed commit to `135.106.186.210`, supplies private business config and 4 tokens, performs one `--send`, records a `SENT` run with SHA-256 lineage/message ID, and the founder confirms receipt.
