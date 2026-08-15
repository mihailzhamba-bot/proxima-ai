# Coding Agents Standard

Scope: this standard is canonical for all Proxima AI repositories. The sibling source
repositories `torgstat-collector` and `proxima-ai-manager` are read-only provenance
sources and are out of scope (see `.planning/PROJECT.md`, Source Boundaries).

## Supported agents

Two terminal coding agents are supported:

- **Claude Code**
- **Codex**

Both are equal first-class agents for any task in this repository: TypeScript
collector/data-plane, Python control-plane, infrastructure, migrations,
documentation. Agent choice per task belongs to the engineer running it.

## Access model

- The only supported access path is the vendor subscription of the corresponding
  agent (Anthropic subscription for Claude Code, OpenAI subscription for Codex).
- API pay-as-you-go billing is not used for regular interactive development.
  Regular means day-to-day coding, review and documentation work in this
  repository.
- Examples that fall under the exception process instead: batch evaluation runs,
  a CI bot, or a one-off script that must call the vendor API directly.
- Any such exception requires a separate Jira task in project PA stating: the
  reason, the owner, a monthly spend limit and a review date. No exception is
  implied by silence or habit.
- Vendor subscription credentials are personal. They are never shared with
  third-party agents or tools.

## Review process

Agent usage does not change the review gate. The binding rule lives in
`.planning/STATE.md`: independent cross-model review with 0 blockers / 0 warnings
is mandatory for phases 3, 4 and 7; all other work ships with root `make verify`,
CI evidence and self-review in EVIDENCE.md.

## Credentials hygiene

- No API keys, billing data or vendor subscription credentials in Git, project
  prompts, shell history or tracker issues.
- Secret locations and modes are defined in `docs/operations/business-signal-runbook.md`
  (`/etc/proxima-ai/secrets/` on the VPS, owner `proxima-admin`, mode `0600`).
  That runbook is the authority; this file does not restate its content.

## Changing this standard

Changes go through a Jira task in project PA plus a commit to this file. Do not
fork the standard in project prompts or per-repository copies.
