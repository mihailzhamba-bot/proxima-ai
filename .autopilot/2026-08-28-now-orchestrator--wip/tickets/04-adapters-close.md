# 04 - R3: три adapters, supervised dispatch и close transaction

**Требования:** R01, R03, R06, R07, R08, R12, R13, R16, R17, G01, G02
**Blocked by:** 01, 02, 03
**Зона:** `.claude/commands/` · `.codex/skills/` · `.codex/config.toml` · `.opencode/commands/` · `.opencode/skills/` · `.opencode/agents/` · `docs/agent-system/` · `docs/release-gates/` · `tools/now_orchestrator/integration/` · `scripts/agent/now` · `tools/tests/test_now_adapters.py`
**Волна:** 4
**Status:** ready

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

- [ ] Claude Code, Codex и opencode adapters определяют `/now` и `/now go <KEY>` и вызывают один core contract.
- [ ] Одна golden fixture даёт byte-identical card body для всех adapters; adapters не ранжируют сами.
- [ ] Release Gate assets присутствуют в branch и переиспользуются; если импортируются из dirty parent, только exact allowlist + SHA-256 без mutation источника.
- [ ] Jira write tools в Codex allowlist совпадают с установленной Atlassian MCP schema; `codex mcp list` green.
- [ ] Dispatch проходит только после confirmation/claims и создаёт существующий Orca supervised flow, не второй engine.
- [ ] Ops close stages только owned files, не содержит `git add -A`, не merge/deploy автоматически.
- [ ] Targeted tests, adapter structural smoke и `make verify` green; independent reviewer 0 blocker.
