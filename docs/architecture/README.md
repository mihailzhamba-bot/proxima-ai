# Архитектура PROXIMA AI M1

Начинать с `system.mmd`: это mind map всей логики M1. Остальные схемы отвечают на 3 отдельных вопроса:

1. `data-flow.mmd` - как source bytes проходят immutable evidence, parsing, quarantine и independent domain releases.
2. `deployment.mmd` - что живет на одном VPS и какие сетевые границы закрыты.
3. `delivery.mmd` - почему следующая часть не начинается до `make verify` и independent review с 0 blocker / 0 warning.

`make architecture` рендерит каждый `.mmd` в SVG и PDF внутри `build/architecture/`. Build outputs не хранятся в Git: источником истины остаются Mermaid-файлы.

На ephemeral GitHub-hosted runner Chromium запускается с CI-only `tools/puppeteer.ci.json`, потому что AppArmor runner запрещает user namespaces. Локальный render использует стандартный Chromium sandbox.

Сплошная стрелка означает реализуемый M1 path. Пунктир означает supporting, blocked или deferred path. Torgstat в M1 существует только как supporting-source contract и не имеет browser/session entrypoint.
