# 01 - R0: snapshot, selector и единые карточки

**Требования:** R01, R02, R03, R04, R09, R10, R11, R13, R14, G02
**Blocked by:** -
**Зона:** `tools/now_orchestrator/core/` · `tools/now_orchestrator/__init__.py` · `scripts/agent/now` · `tools/tests/test_now_core.py` · `.claude/commands/now.md` · `.codex/skills/now/SKILL.md` · `.opencode/commands/now.md`
**Волна:** 1
**Status:** ready

## Что должно заработать

Три thin adapters вызывают один CLI. CLI принимает versioned normalized snapshot JSON и byte-identically рендерит карточки Track B, C, A плюс D FROZEN. Selector использует только hard rules: continue, close, unblock, start, Jira priority, smallest safe slice, stable key. Missing/stale/conflicting sources дают diagnostic recovery card и запрещают action plan.

## Из брифа, дословно

> «а какую сейчас приоритет на задачу делать по проекту?»
> «гипп обязательно в изучении того, что уже есть готовое»
> «Он говорит, вот это задачу всё.»

## Разделы спецификации

Истории 1-8, 17-20, 23-24, 32; Решения 1-2; Границы `snapshot`, `selector`, `renderer`.

## Критерии приёмки

- [ ] Versioned snapshot имеет отдельные Jira, Git, Orca, HANDOFF, TASKS и active ExecPlans sections с freshness.
- [ ] Unsupported schema version, malformed mandatory payload и structural card injection дают BLOCKED.
- [ ] Golden fixture выдаёт один стабильный output в порядке B, C, A и D FROZEN.
- [ ] Claude Code, Codex и opencode read-only `/now` adapters вызывают один CLI и не содержат собственной ranking logic.
- [ ] Каждая A/B/C card содержит key, outcome, owner, blockers, AC, DoD, zones, sources и `captured_at`.
- [ ] Selector приоритетит lifecycle closure внутри каждого трека, блокирует track при active foreign-lane task, учитывает dependency critical path и использует deterministic tie-break; global recommendation остаётся B > C > A.
- [ ] Missing/stale/conflicting mandatory source возвращает BLOCKED без mutation intent.
- [ ] Targeted tests green; CLI help и fixture render smoke green.
