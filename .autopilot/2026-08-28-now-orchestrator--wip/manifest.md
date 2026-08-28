# Манифест требований

Источник: `2026-08-28-brief.md`. Строку из этого списка может снять **только пользователь**.

Подробные решения grill зафиксированы в утверждённом Gate `RG-20260828-now-orchestrator`; они не выдаются здесь за дословные цитаты Mike.

| ID | Из брифа (дословно) | Статус | Основание | Где |
|----|---------------------|--------|-----------|-----|
| R01 | «мне необходим некий оркестратор в проекте» | done | T01 reviewed; full gate green | T01, T04 |
| R02 | «а какую сейчас приоритет на задачу делать по проекту?» | done | T01 reviewed; full gate green | T01 |
| R03 | «Чтобы это было целостно, безпроблем на в плане последовательности» | done | T01 reviewed; full gate green | T01, T04 |
| R04 | «то есть мы сейчас делаем вот-вот раз-два-три» | done | T01 reviewed; full gate green | T01 |
| R05 | «Пока не закончим, не касаемся.» | in-ticket | - | T03 |
| R06 | «он контролирует эти процессы у меня» | in-ticket | - | T03, T04 |
| R07 | «проверяет целостность того, что мы сделали» | in-ticket | - | T04 |
| R08 | «закрепляет, и мы потом идём дальше» | in-ticket | - | T03, T04 |
| R09 | «мне нужно максимальное погружение этот вопрос» | done | T01 reviewed; full gate green | T01 |
| R10 | «гипп обязательно в изучении того, что уже есть готовое» | done | T01 reviewed; full gate green | T01 |
| R11 | «решение обязательно в конце» | done | T01 reviewed; full gate green | T01 |
| R12 | «полностью автономны агент» | in-ticket | - | T03, T04 |
| R13 | «которому я прихожу, говорю, Что делаем сейчас» | done | T01 reviewed; full gate green | T01, T04 |
| R14 | «Он говорит, вот это задачу всё.» | done | T01 reviewed; full gate green | T01 |
| R15 | «если он видит чего-то не хватает, он также добавляет это» | in-ticket | - | T02 |
| R16 | «работа с жирой» | in-ticket | - | T02, T04 |
| R17 | «ксмально развёрнуто всё пишет» | in-ticket | - | T02, T04 |
| R18 | «подписывается задача» | in-ticket | - | T02 |
| G01 | «после отдай в $autopilot» | in-ticket | дополнение Mike от 2026-08-28 | T04 |
| G02 | «Implement the plan.» | in-ticket | Mike утвердил Gate `RG-20260828-now-orchestrator` | T01, T02, T03, T04 |

## Adversarial pass

- Провал: Mike не вызывает `/now` - отслеживается 14-дневным kill condition, не расширяет build.
- Столкновение: «полностью автономны агент» конфликтует с merge/deploy gate - автономность заканчивается на merge gate по решению Mike.
- Непроверенное: live Jira может расходиться с Git - snapshot всегда reconciles Jira, Git/PR/worktrees, Orca и repo mirrors.
- Цена: safe Jira writes несут основной риск - allowlist, pre-write ledger и fixture-first tests обязательны.
- Вторая неделя: leaked lock или пересечение зон останавливают старт; нужен recovery path и один integration lock.
