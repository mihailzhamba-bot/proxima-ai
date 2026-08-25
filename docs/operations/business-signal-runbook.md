# Business signal - staging runbook

Phase 2.1 запускается вручную на Selectel VPS `135.106.186.210`. Это staging exception для кабинета `amirova-test`: production release pointer, Data GO и Live Deploy GO не меняются. Scheduler и автоматический повтор Telegram отсутствуют.

## SSH access rule

```bash
ssh proxima         # shell на VPS под proxima-admin
ssh -N proxima-db   # туннель к Postgres на localhost:5433
bash infra/ssh-doctor   # диагностика, если что-то не работает
```

Алиасы описаны в `~/.ssh/config` на машине Mike. Ключ - `~/.ssh/id_ed25519_proxima_selectel_20260813`
(`SHA256:CG+iddsvx2qxzSjJXC2v8nztu5LxkOb73ekmEYDNTXM`), защищён passphrase из macOS Keychain.
Обязательны две опции: `IdentitiesOnly yes` (на сервере `MaxAuthTries 3`, перебор лишних ключей рвёт
сессию) и `UseKeychain yes` (без неё ssh не читает passphrase и падает в `Permission denied (publickey)`
при полностью исправном сервере).

**Только `proxima-admin`.** Root заблокирован при bootstrap намеренно: `PermitRootLogin no`,
`AllowUsers proxima-admin`, `passwd --lock root` (`infra/bootstrap/00-proxima-ai.conf`,
`bootstrap-vps.sh:139`). `ssh root@135.106.186.210` не может сработать никогда - если такая команда
где-то записана, это ошибка инструкции, а не проблема доступа.

**VPN подключению не мешает.** Прежняя редакция этого раздела утверждала обратное («Selectel фильтрует
TCP/22 через зарубежный egress»). Перепроверено 2026-08-22 при активном AmneziaVPN (full tunnel `utun4`):
TCP/22 открывается за 0.148 s, ICMP 3/3, RTT 140 ms, host key совпадает с `known_hosts`. Ручной
`sudo route add` не нужен. Если хост всё же надо вывести из туннеля - добавить его в список исключений
самой Amnezia (Настройки → Раздельное туннелирование → Сайты); маршрут восстанавливается при реконнекте
и после ребута, в отличие от ручного route.

Быстрая проверка, сеть ли виновата: `nc -z 135.106.186.210 22`. Порт открылся - сеть ни при чём,
причина в аутентификации; `bash infra/ssh-doctor` покажет, в какой именно.

## Private files

Все файлы ниже создаются на VPS с owner `proxima-admin` и mode `0600`. Их значения не попадают в Git, shell history, PostgreSQL logs или evidence:

- `/etc/proxima-ai/secrets/wb_statistics_token` - отдельный READ-only token только категории Statistics;
- `/etc/proxima-ai/secrets/wb_analytics_token` - отдельный READ-only token только категории Analytics;
- `/etc/proxima-ai/secrets/wb_finance_token` - отдельный READ-only token только категории Finance;
- `/etc/proxima-ai/secrets/telegram_bot_token` - token бота, созданного через BotFather;
- `/etc/proxima-ai/business-signal/founder-chat.json` - private source с единственным числовым полем `chat_id`; значение основателя захардкожено только в этом private-файле;
- `/etc/proxima-ai/business-signal/products.csv` - `tenant_id,nm_id,internal_article,cogs_rub,lead_time_days,safety_buffer_days,effective_from`;
- `/etc/proxima-ai/business-signal/warehouses.csv` - `tenant_id,sales_warehouse_name,stock_warehouse_name,canonical_warehouse,effective_from`. Важно: pipeline загружает mappings с `effective_from <= window.to` (конец 14-дневного окна, вчерашний день). Новую строку датировать началом окна или раньше, иначе она невидима до завтра и run остаётся `WAREHOUSE_MAP_MISSING`. Sales-строки и stock-строки маппятся независимо: WB может прислать продажу со служебным складом (например «Склад WB РФ»), которого нет в stock-отчёте, - ему тоже нужна строка.

Нельзя переиспользовать широкий token: CLI декодирует JWT scope и блокирует запуск, если token не READ-only или содержит больше одной нужной категории. Незнакомые scope-биты тоже отвергаются.

Для Day 1 probe дополнительно нужны `/etc/proxima-ai/secrets/wb_prices_token` и `/etc/proxima-ai/secrets/wb_promotion_token` (READ-only, exact-category). Они не входят в business-signal bundle installer: оператор устанавливает их вручную с owner `proxima-admin` и mode `0600`, как statistics token.

Временное исключение для staging: exact-category Analytics token в режиме RW допускается только явным флагом `--allow-analytics-read-write`. Флаг не разрешает дополнительные категории и не ослабляет Statistics/Finance. Тот же флаг принимает Day 2 коллектор `tools/wb_async_report.py` (Makefile-таргет `collect-wb-analytics` флаг не передаёт - добавлять в команду явно). Удалить исключение после выпуска Analytics READ-only token.

Подготовить private bundle вне Git с семью файлами из списка выше, используя короткие имена `wb_statistics_token`, `wb_analytics_token`, `wb_finance_token`, `telegram_bot_token`, `founder-chat.json`, `products.csv`, `warehouses.csv`. Каждый source-файл должен иметь mode `0600`. Значения не передавать через shell arguments. После безопасной доставки bundle на VPS проверить и установить его одной командой:

```bash
sudo bash /srv/proxima-ai/repo/infra/bootstrap/install-business-signal-inputs.sh \
  amirova-test /absolute/private/bundle --allow-analytics-read-write
```

Installer сначала копирует bundle во временный private staging, переиспользует runtime validators для трёх WB scopes, Telegram token shape, founder chat и обеих CSV, затем устанавливает проверенные файлы с owner `proxima-admin` и mode `0600`. При validation failure существующие runtime inputs не меняются. Source bundle после подтверждённой установки удаляет сам оператор.

Founder `chat_id` вручную искать не нужно. После создания бота через BotFather записать token в `telegram_bot_token`, отправить этому боту `/start` из Telegram-аккаунта основателя и выполнить:

```bash
node /srv/proxima-ai/repo/services/collector/dist/cli/discover-founder-chat.js \
  --telegram-token-file /home/proxima-admin/signal-inputs/telegram_bot_token \
  --founder-chat-source /home/proxima-admin/signal-inputs/founder-chat.json
```

CLI работает только при отключённом webhook, требует ровно один private chat с `/start`, ничего не отправляет и атомарно записывает private `chat_id` с mode `0600`. Если `/start` прислали разные аккаунты, discovery блокируется.

## Deploy without live send

1. Записать baseline commit VPS и сделать private `pg_dump` до migration.
2. Доставить проверенный clean commit через `git bundle` в detached checkout. Не делать `git pull` поверх dirty tree.
3. Запустить `infra/bootstrap/prepare-business-signal-runtime.sh` от root. Скрипт ставит Node 22.x, проверяет major version, выполняет `npm ci` и `npm run build`.
4. Применить ordered migration через существующий `tools/apply_migrations.py`.
5. Создать 7 private files из списка выше. Не вставлять secret values в аргументы команд.
6. Загрузить versioned config:

```bash
runuser --user proxima-admin -- node /srv/proxima-ai/repo/services/collector/dist/cli/seed-signal-config.js \
  --database-url-file /etc/proxima-ai/secrets/postgres_url \
  --products-csv /etc/proxima-ai/business-signal/products.csv \
  --warehouses-csv /etc/proxima-ai/business-signal/warehouses.csv
```

7. Выполнить dry run без Telegram:

```bash
runuser --user proxima-admin -- node /srv/proxima-ai/repo/services/collector/dist/cli/stockout-signal.js \
  --tenant amirova-test \
  --database-url-file /etc/proxima-ai/secrets/postgres_url \
  --raw-root /srv/proxima-ai/data/business-signal \
  --statistics-token-file /etc/proxima-ai/secrets/wb_statistics_token \
  --analytics-token-file /etc/proxima-ai/secrets/wb_analytics_token \
  --finance-token-file /etc/proxima-ai/secrets/wb_finance_token \
  --allow-analytics-read-write
```

Dry run должен завершиться `READY`, `NO_SIGNAL` или typed `BLOCKED`. До parse каждый WB response уже лежит byte-for-byte в content-addressed store с SHA-256 manifest и строкой `business_signal_raw_artifacts`. Манифесты raw store существуют в двух версиях: `schema_version: 1` (до 2026-08-14, без `response_headers`) и `schema_version: 2` (с allowlisted rate-limit заголовками). Верификаторы обязаны принимать обе. В БД `response_headers IS NULL` означает строку до внедрения захвата заголовков, пустой объект - заголовки собраны, но WB не прислал ни одного allowlisted.

Семантика детектора (зафиксировано 2026-08-14):

- Сигнал срабатывает строго при `daysCover < leadTimeDays + safetyBufferDays`. Равенство порогу сигналом не считается.
- SKU с остатком, но без продаж в окне 14 дней не создаёт сигнал и не блокирует run; он перечисляется в поле `new_sku_no_history` вывода CLI.
- SKU с продажами, но без строк «Продажа» в Finance-отчёте исключается из кандидатов и перечисляется в поле `margin_missing`; run продолжается по остальным SKU.
- Неожиданно пустой sales- или stock-ответ по активному кабинету даёт `BLOCKED` (`WB_SALES_EMPTY` / `WB_STOCKS_EMPTY`) до ручного разбора.

## One live attempt

После проверки dry run запустить ту же команду один раз с тремя дополнительными аргументами:

```text
--send
--telegram-token-file /etc/proxima-ai/secrets/telegram_bot_token
--founder-chat-source /etc/proxima-ai/business-signal/founder-chat.json
```

CLI сначала вызывает Telegram `getMe` и `getChat`, затем делает один `sendMessage`. При timeout или reject второй `sendMessage` не выполняется. Run получает `SEND_FAILED`; повтор возможен только новым ручным решением.

Проверка acceptance:

- один run со status `SENT`, Telegram `message_id` и source SHA-256;
- одно сообщение содержит SKU, склад, days cover, срок поставки, buffer и маржу на единицу;
- основатель подтверждает получение.

## Manual dissection: BLOCKED async-report task (wb_analytics_report_tasks)

Задача `wb_analytics_report_tasks` в `BLOCKED` терминальна для CLI (`wb_async_report.py` откажется с "task … is blocked"). Процедура операторской разблокировки добавлена 2026-08-25 после первой такой интервенции (task `f1b8892a…`, dead-token 401). Применять только после ручного анализа причины BLOCKED и её устранения (например, замена мёртвого токена):

1. Убедиться, что raw-evidence причины блокировки сохранён: `raw_wb_analytics_responses` строки этой задачи не удаляются никогда.
2. Вернуть задачу в очередь: `UPDATE wb_analytics_report_tasks SET lifecycle_status = 'RESERVED', last_error_code = NULL, api_status = NULL WHERE task_id = '<uuid>' AND lifecycle_status = 'BLOCKED';`
3. Если initial create уже был помечен отправленным, сбросить ровно один квота-ивент: `UPDATE wb_analytics_quota_events SET sent_at = NULL WHERE task_id = '<uuid>' AND action = 'create' AND action_sequence = 1 AND sent_at IS NOT NULL;`
4. Повторить прогон `wb_async_report.py` обычным путём; задача продолжит lifecycle с create.
5. Зафиксировать интервенцию в phase EVIDENCE (причина, шаги, дата).

Сброс не для автоматизации: каждый случай BLOCKED разбирается руками, условие п.1 обязательно.

WB READ contracts: [Reports](https://dev.wildberries.ru/en/openapi/reports), [Analytics](https://dev.wildberries.ru/en/openapi/analytics), [Finance](https://dev.wildberries.ru/en/openapi/financial-reports-and-accounting). Stock runtime использует current `POST /api/analytics/v1/stocks-report/wb-warehouses`; deprecated stocks и realization endpoints запрещены verifier-ом.
