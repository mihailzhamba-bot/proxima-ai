window.STATE =
{
  "slug": "pmm29-product-contracts-v1",
  "dir": "2026-08-28-pmm29-product-contracts-v1",
  "title": "PMM-29: продуктовые контракты v1, codegen и контрактные тесты",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T1",
  "briefFile": "2026-08-28-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/Users/mikezhamba/.codex/skills/autopilot",
  "startedAt": "2026-08-28T19:44:08+03:00",
  "updatedAt": "2026-08-29T12:06:00+03:00",
  "finishedAt": "2026-08-29T12:06:00+03:00",
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-08-28T19:44:08+03:00", "finishedAt": "2026-08-28T19:50:12+03:00" },
    { "id": "manifest", "status": "done", "startedAt": "2026-08-28T19:50:12+03:00", "finishedAt": "2026-08-28T19:50:12+03:00" },
    { "id": "briefing", "status": "done", "startedAt": "2026-08-28T19:50:12+03:00", "finishedAt": "2026-08-29T11:35:59+03:00" },
    { "id": "spec", "status": "done", "startedAt": "2026-08-29T11:35:59+03:00", "finishedAt": "2026-08-29T11:39:43+03:00" },
    { "id": "plan", "status": "done", "startedAt": "2026-08-29T11:39:43+03:00", "finishedAt": "2026-08-29T11:40:15+03:00", "note": "2 таска, ярус T1, волны 1-2" },
    { "id": "build", "status": "done", "startedAt": "2026-08-29T11:40:15+03:00", "finishedAt": "2026-08-29T11:55:00+03:00", "note": "2 из 2 тасков готовы" },
    { "id": "review", "status": "done", "startedAt": "2026-08-29T11:44:43+03:00", "finishedAt": "2026-08-29T12:02:00+03:00", "note": "T01/T02 reviewed: 0 blockers, 2 non-blocking craft concerns" },
    { "id": "final", "status": "done", "startedAt": "2026-08-29T12:02:00+03:00", "finishedAt": "2026-08-29T12:06:00+03:00" }
  ],
  "requirements": {
    "total": 47, "done": 47, "inTicket": 0, "inSpec": 0,
    "placeholder": 0, "deferred": 0, "dropped": 0
  },
  "tickets": [
    { "id": "01", "title": "Canonical product schemas and verifier", "requirements": ["R01","R06","R08-R37","R40-R43"], "blockedBy": [], "wave": 1, "zone": ["contracts/","tools/verify_contracts.py"], "status": "done", "startedAt": "2026-08-29T11:40:15+03:00", "finishedAt": "2026-08-29T11:49:46+03:00", "retries": 0, "repairs": 1, "repairFindings": ["tools/verify_contracts.py:70-71 - enforce diagnosis positional source_refs invariant for every diagnosis, not only fixed positive fixture"], "handoffs": 0, "files": ["contracts/signal.schema.json","contracts/diagnosis.schema.json","contracts/decision-record.schema.json","contracts/examples/","tools/verify_contracts.py"], "tests": { "passed": 48, "failed": 0 }, "commit": "17c2d51e98d9649e1640d2ea75311947195d1331" },
    { "id": "02", "title": "Generated TypeScript types and Ajv contract tests", "requirements": ["R01-R05","R07","R38-R39","R44-R47"], "blockedBy": ["01"], "wave": 2, "zone": ["services/collector/src/contracts/","services/collector/tests/product-contracts.test.ts"], "status": "done", "startedAt": "2026-08-29T11:49:46+03:00", "finishedAt": "2026-08-29T12:02:00+03:00", "retries": 0, "repairs": 0, "handoffs": 0, "files": ["services/collector/src/contracts/decision-record.ts","services/collector/src/contracts/diagnosis.ts","services/collector/src/contracts/signal.ts","services/collector/tests/product-contracts.test.ts"], "tests": { "passed": 54, "failed": 0 }, "commit": "b20e2e9" }
  ],
  "singlePass": null,
  "tests": { "passed": 260, "failed": 0, "skipped": 4 },
  "debt": { "placeholders": [], "assumptions": [], "emptyEnv": [] },
  "additions": [],
  "coverage": { "found": 2, "fixed": 2, "deferred": 0 },
  "concerns": [
    { "severity": "warning", "path": "services/collector/tests/product-contracts.test.ts:22", "note": "strictRequired:false leaves Ajv strict-required warnings disabled; existing schemas require it for compatibility." },
    { "severity": "warning", "path": "services/collector/tests/product-contracts.test.ts:56-63", "note": "diagnosis positional source_refs invariant is asserted on the positive fixture, while Python verifier has a dedicated negative fixture." }
  ],
  "reviewers": { "manifestSpec": "review_t01", "craft": "review_t02" },
  "blind": { "verdict": "PASS", "note": "No requirement drift; AC1/2/4 implemented, AC3 snapshot_id remains opaque non-empty by approved spec, AC5 structurally covered by closed schemas and glob verifier; no blocking findings." }
}
