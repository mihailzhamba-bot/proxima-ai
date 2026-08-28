# 04 - R3: три adapters, supervised dispatch и close transaction

**Требования:** R07, G01, G02
**Blocked by:** 01, 02, 03
**Зона:** `.claude/commands/` · `.codex/skills/` · `.codex/config.toml` · `.opencode/commands/` · `.opencode/skills/` · `.opencode/agents/` · `docs/agent-system/` · `docs/release-gates/` · `tools/now_orchestrator/integration/` · `scripts/agent/now` · `tools/tests/test_now_adapters.py`
**Волна:** 4
**Status:** READY_COMMIT

## Что должно заработать

Три adapters собирают одинаковый live snapshot, вызывают core, показывают один output и выполняют только выданный action plan. `/now go` переиспользует Release Gate, Autopilot, Orca supervised worker, verify/reviewer и merge gate. Ops sync использует isolated worktree/PR и закрывает repo mirrors после merge. Codex allowlist включает только нужные Jira tools и проходит config smoke.

## Из брифа, дословно

> «мне необходим некий оркестратор в проекте»
> «проверяет целостность того, что мы сделали»
> «после отдай в $autopilot»
> «Implement the plan.»

## Разделы спецификации

Истории 1, 5-6, 11-16, 21-23, 27, 29, 31-35; Решения 1, 3-6; Граница `client adapters`.

## Критерии приёмки

- [x] Claude Code, Codex и opencode adapters определяют `/now` и `/now go <KEY>` и вызывают один core contract.
- [x] Одна golden fixture даёт byte-identical full stdout через три real facade entry; adapters не ранжируют сами.
- [x] Release Gate assets присутствуют в branch и переиспользуются; exact allowlist SHA-256 повторно проверен без mutation источника.
- [x] Codex allowlist совпадает с установленной Atlassian MCP schema: 3 read tools; write tool отсутствует, `codex mcp list` exit 0, close возвращает `BLOCKED_EXTERNAL`.
- [x] Dispatch проходит только после persisted confirmation/claim + Gate readback и создаёт существующий Orca supervised flow, не второй engine.
- [x] Ops close stages только owned files, не содержит `git add -A`, не merge/deploy автоматически.
- [x] Targeted tests, adapter structural smoke и `make verify` green; independent reviewer 0 blocker / 0 warning.

Machine evidence 2026-08-28 after repair-cycle 3 on base HEAD `b523d1072aefe5aa53284f7ddc811c06bd70eb87`: canonical targeted `tools/tests/test_now_*.py` 118 passed, exit 0; final `make verify` exit 0, 264 passed / 4 skipped. Independent final re-review: 0 blockers / 0 warnings. T04 remains uncommitted and READY_COMMIT; no live Jira/Orca/GitHub/merge/deploy effect occurred.

## Exact import allowlist из dirty parent

- `.opencode/skills/release-cutter/SKILL.md` - `6a97d0238c3675a9b0c5e7b977dab48ceb64541036ad09cea8c324a6a00dfc98`
- `.opencode/agents/release-critic.md` - `e76fa380998e272ac4b0bcb35c15f9fa86e14a98cb39c4451aca3393e145253f`
- `.opencode/commands/release-gate.md` - `f59ed9157528af83fd7cf0b47265ca4ae660585ff91b5e18efa46ae12e33d2fa`
- `.opencode/commands/release-task.md` - `349e5b3adb5346a21734f7aabbc6f9325b2d978256e32ed7ffb06c7d420a50cb`
- `docs/release-gates/README.md` - `55611117357914bdb5a26d7ae9bc0243e9820287af6bfa87ee88af899b772016`

Источник: parent checkout `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PROXIMA AI`, read-only. Любой hash mismatch блокирует импорт. Фактический merge/deploy/Jira write в T04 implementation run не выполняется.
