# Phase 2 Context - Vertical Slice: Immutable Intake to Visible Facts

## Locked decisions

- This phase admits only an official manual WB XLSX through one TypeScript intake path. It does not activate WB API clients, Torgstat sessions, advertising APIs, writes, or a public UI.
- Input bytes are copied and SHA-256-addressed before workbook parsing. Raw evidence, manifests and temporary recovery material live under an operator-supplied private directory outside the Git worktree.
- The content digest is the artifact identity. A repeat with identical bytes and canonical metadata is idempotent; metadata that conflicts with the already-recorded artifact is rejected and is never silently overwritten.
- A raw object without its manifest is recovery material, not public state. The manifest is the publication marker. A retry finalizes it without making duplicate artifacts or facts.
- Slice tables use ordered additive migrations beginning at `002_`; no throwaway schema or release pointer is allowed. Phase 3 owns full quality, quarantine, roles and atomic releases.
- The only slice presentation is a localhost-bound, read-only preview explicitly marked `unreleased`. It may show no raw bytes, secrets, customer payloads or production release status.
- Test fixtures are synthetic structural workbooks. Real pilot XLSX bytes and business values remain outside Git.

## External input required for the parser slice

Mike must provide one official WB XLSX export from the Bogatova/Belle Robe cabinet whose rows identify calendar day, product/SKU (or `nmId`) and order count. The file may be placed in a private local directory or attached to the workspace, but must not be copied into Git. Before writing the parser, record only its header names, sheet names, byte size and SHA-256 in phase evidence; do not commit cells or business values.

## Failure contract

- A crash before raw publication leaves only a private temporary file, which is safe to remove during the next recovery pass.
- A crash after raw publication and before manifest publication leaves an immutable orphan raw object; retry either finalizes the exact manifest or returns a typed metadata-conflict error.
- The intake never parses, stages, creates facts or advances a pointer before raw and manifest publication have succeeded.
- Manifest-to-raw checksum mismatch is a typed quarantine condition. It never moves a pointer and is preserved as evidence for Phase 3's complete quality workflow.

