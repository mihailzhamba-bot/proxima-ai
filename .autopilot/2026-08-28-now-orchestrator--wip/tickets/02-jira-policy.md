# 02 - R1: Jira policy, pre-write ledger и safe repair

**Требования:** R15, R16, R17, R18, G02
**Blocked by:** 01
**Зона:** `tools/now_orchestrator/jira/` · `scripts/agent/now` · `tools/tests/test_now_jira.py` · `.claude/commands/now.md` · `.codex/skills/now/SKILL.md` · `.opencode/commands/now.md` · `.codex/config.toml`
**Волна:** 2
**Status:** done

## Что должно заработать

Core классифицирует Jira intent до MCP call, записывает safe digest в append-only ledger и возвращает AUTO, APPROVAL_REQUIRED или DENY. Три adapters используют этот contract перед каждым Atlassian MCP write и записывают remote outcome только для ранее авторизованного intent. Safe gap получает create/link/comment/edit plan; неоднозначный или scope-changing gap не мутируется. Codex project allowlist включает только подтверждённые installed write tools.

## Из брифа, дословно

> «если он видит чего-то не хватает, он также добавляет это»
> «работа с жирой»
> «ксмально развёрнуто всё пишет, подписывается задача»

## Разделы спецификации

Истории 25-30, 32; Решения 4; Граница `jira_policy`.

## Критерии приёмки

- [x] AUTO разрешает только single-issue create/edit/comment/link/assign-Mike/transition внутри PA/PMM.
- [x] Delete/archive/bulk, foreign project, assignee не Mike и epic/scope replacement дают APPROVAL_REQUIRED или DENY без side effect.
- [x] Ledger intent создаётся до внешнего call и хранит digest, actor, operation, project/key, timestamp и decision без полного payload/secrets.
- [x] Outcome нельзя записать без существующего authorized intent; retry требует live reconciliation.
- [x] In-scope blocker получает link к current task; out-of-scope safe gap становится backlog plan; ambiguous gap остаётся proposal.
- [x] Три adapters выполняют audit-before-write flow одинаково и не обходят policy core.
- [x] `.codex/config.toml` allowlist использует только реальные Atlassian MCP tool names; `codex mcp list` green.
- [x] Targeted policy/ledger tests green; live Jira mutation не выполняется без designated throwaway issue.
