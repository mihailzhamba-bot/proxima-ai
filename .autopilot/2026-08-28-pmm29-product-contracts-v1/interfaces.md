# Что уже построено

Читается каждым исполнителем до начала работы. Не изобретай заново то, что здесь есть.

## Границы, решённые в спецификации

- `contracts` владеет canonical JSON Schemas и synthetic examples; выставляет schema files для verifier/codegen; прячет consumer runtime.
- `contract-verifier` владеет discovery и negative diagnostics в `tools/verify_contracts.py`; выставляет command behavior; прячет TS/Ajv details.
- `contract-codegen` владеет schema-to-TypeScript generation; выставляет `make codegen`; generated files не редактируются вручную.
- `contract-tests` владеет real Ajv positive/negative assertions; выставляет npm test seam; не меняет production consumers.
- Shared signal shape: `detection_data[key] -> {value: number|string|boolean|null, is_unknown: boolean}`; `null + true` = UNKNOWN, `0 + false` = measured zero.
- Shared decision metric shape: `{name: string, value: number, unit: string, source_ref: string}`; `actual`/`delta` are null or the same metrics object.

## Общие правила проекта

- Node >=22 <23; TypeScript collector workspace; Python 3.14 only via uv.
- Commands: `npm install` in worktree before verification; `make codegen`; `npm test`; `make contracts`; `make verify`.
- Existing M1 schemas/examples, Makefile, README/docs, secrets, auth/infra and sibling worktrees are out of scope.
- Generated `services/collector/src/contracts/*.ts` are codegen-owned and must never be hand-edited.
- Synthetic fixtures only; no real cabinet IDs, SKU, prices, tokens or credentials.
- If a dependency is missing, do not add it; return `BLOCKED` with its name.

## Из таска 01 — контрактное ядро

- Three canonical v1 schema files and positive/negative examples.
- Verifier discovers all schema files and reports invalid negative fixture paths.
- Schema IDs: `https://proxima.local/contracts/<name>/v1`; `schema_version` const 1.
- Diagnosis refs use positional invariant: `source_refs.length = 1 + alternatives.length + unknowns.length`.
- T01 exposed `SignalV1`, `DiagnosisV1`, `DecisionRecordV1`; verifier now discovers schemas and `-bad-` fixtures with field paths.

## Из таска 02 — generated/test seam

- `make codegen` is the only producer of TypeScript contract types.
- Ajv2020 strict validation with `allErrors:true` and `ajv-formats` is the TS test boundary.
 T02 exposed generated SignalV1, DiagnosisV1, DecisionRecordV1, Measurement and Metric helper types; product-contracts.test.ts covers positive/negative Ajv paths.
