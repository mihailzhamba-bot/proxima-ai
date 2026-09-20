# Bootstrap-инструменты

Эти файлы запускает оператор релиза на VPS, если ниже не указан другой исполнитель.

- `00-proxima-ai.conf` — параметры sysctl для хоста; устанавливает `bootstrap-vps.sh`.
- `bootstrap-vps.sh` — первичная подготовка хоста; запускает оператор от root.
- `install-business-signal-inputs.sh` — устанавливает входы business-signal; запускает оператор.
- `prepare-business-signal-runtime.sh` — готовит runtime-каталоги business-signal; запускает оператор.
- `prepare-day1-runtime.sh` — готовит каталоги и права первого дня; запускает оператор.
- `provision-analyst-role.sh` — создаёт read-only LOGIN-роль аналитика; запускает Mike после runtime-provision.
- `provision-postgres-diagnostics.sh` — создаёт диагностическую роль и устанавливает read-only wrapper; запускает оператор от root.
- `provision-runtime-roles.sh` — создаёт runtime-роли, гранты и URI-файлы; запускает оператор после миграций и перед ними.
- `proxima-psql-owner` — запускает owner `psql` в production-контейнере; оператор устанавливает как root mode `0755` для `provision-runtime-roles.sh`.
- `proxima-psql-readonly` — запускает диагностический read-only `psql`; устанавливает `provision-postgres-diagnostics.sh`.
