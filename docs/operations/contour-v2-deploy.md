# CONTOUR-V2-DEPLOY — runbook релиза контура LOOP v2 (код + политика)

База runbook: ветка `server/loop-continuous` (clone 18.09.2026), файлы `infra/loop-control/install.py`, `compose.yaml`, `tools/loop/{continuous_queue,continuous_receiver,continuous_register,continuous_admission,continuous_base_refresh,continuous_tick,runner}.py`. Все команды сверены с кодом; домыслы помечены в §8 «Неуверенности».

Хосты (факты оператора):
- control = mckenzie 135.106.211.149: compose-стек `loop-control` в `/opt/loop-control`, контейнер `loop-control-bridge-1`, bridge API `127.0.0.1:18770`.
- runner = harper 135.106.211.64: `loop-runner.service` (user verifier uid 1000), код `/opt/loop/*`, приёмка `/opt/loop-review/*`, bridge через reverse-tunnel `127.0.0.1:18771`.
- worker = claudette 135.106.186.210: `/etc/loop-worker/*`, seal-скрипт `/usr/local/sbin/loop-worker-seal`, dispatch по forced-SSH (`97-loop-worker-sshd.conf`, ForceCommand `/opt/loop/worker_ssh.py`).

Опорные значения:
- старый policy fingerprint: `91df66f657aaec8e2be937de3ee072c025cf0cded5c3204913d79663a7d49328` (все три приёмника синхронно);
- новая база (feat/loop-pilot): `01f3e2973444747ca9182155be640afec8ed4538`;
- новая политика: `policy_id = wb-continuous-v2`, fingerprint вычисляется от контента (см. §5, шаг 0);
- очередь на паузе: bridge `POST /v1/pause` (операторский токен `/etc/loop/secrets/bridge_operator`).

Важная поправка к известному контексту: по коду приёмников (`continuous_receiver.py:18-25,77-81`) fingerprint каждого приёмника читается из `/etc/loop-continuous/receiver.json` (поле `policy_fingerprint`) на КАЖДОМ хосте, а не из `/etc/loop-worker/templates.json`. `templates.json` (worker) и `bridge.json → templates` (control) и `/etc/loop-runner/config.json → templates` (harper) хранят зарегистрированные шаблоны (base_sha, prompt_file), но не policy fingerprint. Полный список мест синхронизации - §5.

---

## 1. Предусловия

1.1. Очередь на паузе. Проверка (на mckenzie):
```
TOKEN=$(sudo cat /etc/loop/secrets/bridge_operator)
curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:18770/v1/queue | python3 -m json.tool
```
Ожидаемо: `"queue_paused": true`. Пауза обязательна: при `queue_paused=false` тик (`continuous_tick.py:34-37`) уходит в планирование/admission/dispatch, и любое расхождение fingerprint по хостам станет живым отказом регистрации. Пауза также блокирует dispatch на bridge (`bridge.py:463,473,544`).

1.2. Зафиксировать состояние очереди: из `/v1/queue` сохранить список items и их `state`. Элементы в `proposed/registering/ready/dispatching/running/unknown` несут СТАРЫЙ `policy_fingerprint`; после смены политики код очереди выбирает только элементы с текущим fingerprint (`continuous_queue.py:385`), т.е. недошедшие элементы «замораживаются» вне конвейера. Решение: дождаться их завершения/слияния до релиза либо осознанно принять заморозку (ID записать в журнал релиза). In-band реаннимации вручную нет - только поток advance_base.

1.3. Зелёный CI на релизном коммите ветки `server/loop-continuous`; в репо на этом коммите лежит обновлённый `infra/loop-control/continuous.policy.example.json` с контентом `wb-continuous-v2` (install.py деплоит на хосты именно этот файл, `install.py:56,86,114`). Все requirements политики должны иметь `base_sha = 01f3e2973444747ca9182155be640afec8ed4538` и проходить `validate_policy` (`continuous_queue.py:26-58`).

1.4. Вычислить и записать новый fingerprint (в любом root-checkout репо релизного коммита):
```
python3 -c 'import json,sys; sys.path.insert(0,"tools/loop"); from continuous_queue import validate_policy,digest; print(digest(validate_policy(json.load(open("infra/loop-control/continuous.policy.example.json")))))'
```
Далее по тексту: `<NEW_FP>`. Проверка валидности политики важна: receiver на каждом хосте повторяет `validate_policy` и сравнивает digest, иначе fail closed (`continuous_receiver.py:80-81`).

1.5. Бэкапы (два слоя):
- install.py сам делает снапшот при каждом `--apply`: `/var/backups/loop-install/<UTC-штамп>-<pid>/` c `manifest.json` и копией каждого таргета (имя = sha256 пути), плюс снимок enabled/active состояния юнитов; при любой ошибке apply откатывает файлы и юниты сам (`install.py:226-263,756,777-782`).
- Конвенция оператора для РУЧНЫХ правок (bridge.json, receiver.json, config.json, templates.json, нативный оверрайд): перед каждым изменением `sudo cp -a <файл> <файл>.before-v2-<UTC-штамп>` рядом с файлом. Эти файлы install.py не трогает и в снапшот не кладёт (кроме templates.json на worker, который install.py создаёт только если его нет, `install.py:664-666`).

1.6. На каждом хосте должен быть root-owned checkout репо на релизном коммите: install.py резолвит источники от своего пути (`ROOT = Path(__file__).resolve().parents[2]`, `install.py:28`), т.е. запускается как `python3 infra/loop-control/install.py --role X ...` из корня checkout. На mckenzie кандидат - `/srv/loop/source/proxima-ai` (`LOOP_SOURCE_REPO` в `loop-continuous.service`); на harper/claudette путь операторского install-checkout - UNKNOWN (см. §8.3). Найджеллинг: на harper `/srv/loop-runner/source/proxima-ai` - это рабочий checkout verifier-а для dispatch, не факт что он годится как источник install.

---

## 2. Роль install.py -> хост -> что обновит -> сервисы к рестарту

Запуск: `sudo python3 infra/loop-control/install.py --role <role> --check|--apply` (apply только root, `install.py:753`). `--check` считает три списка: `public_drift` (расхождение публичных файлов), `missing_private_or_runtime`, `verification_errors`; `status: ready` только при пустых всех трёх.

| Роль | Хост | Что обновит (ключевое, полный словарь в install.py:36-136) | Рестарт при --apply |
|---|---|---|---|
| control | mckenzie | `/opt/loop/{bridge,continuous_queue,continuous_base_refresh}.py`, `/opt/loop/continuous_{dispatch(755),admission,merge_observer,existing_work,report,report_sender(755),report_once(755),tick(755),register(755),proposal-review(755)}.py`, `/opt/loop/{telegram,night_batch(755),glm_review,model_router}.py`, `/etc/loop/native/director_tool.py`, `/usr/local/sbin/loop-continuous-register`, `/etc/loop-continuous/policy.json` (0600, ПЕРЕЗАПИШЕТ живой), `/opt/loop-control/compose.yaml`, `/etc/loop/10-paperclip-role.sh`, `/etc/loop/openhands_relay.py`, `/etc/loop-proxy/tinyproxy.conf`, logrotate, юниты incl. `loop-continuous.{service,timer}` в `/etc/systemd/system` | `systemctl enable+restart`: loop-egress-tunnel, loop-egress-proxy, loop-openhands-tunnel, loop-openhands-relay, loop-network-preflight, **loop-control.service** (=bounce всего compose-стека: postgres, paperclip, hermes, bridge), loop-backup.timer, loop-health.timer (`install.py:648`). **loop-continuous.service НЕ рестартует** - это oneshot по таймеру, каждый запуск читает код заново |
| runner | harper | `/usr/local/sbin/loop-continuous-register`, `/opt/loop/{continuous_dispatch(755),continuous_admission,night_batch(755),glm_review,model_router,continuous_register,continuous_queue,continuous_base_refresh,runner(755),bridge,publication,push_gate,verify_candidate,history_gate(755),loopctl(755)}.py`, `/opt/loop/secret_scan.py`, `/opt/loop-review/continuous-acceptance` (набор приёмки + `manifests/0153b16…json`), `/opt/loop-review/review-candidate`, sudoers, `/etc/loop-continuous/policy.json` (0600, ПЕРЕЗАПИШЕТ живой), юниты `loop-runner-bridge-tunnel.service`, `loop-runner.service` | `systemctl daemon-reload` + `enable+restart loop-runner-bridge-tunnel.service loop-runner.service` (`install.py:748,102`) |
| worker | claudette | `/usr/local/sbin/loop-continuous-register`, `/opt/loop/{continuous_register,continuous_queue,continuous_base_refresh,continuous_feedback,worker_prompt,bridge}.py`, `/opt/loop/{worker_dispatch,worker_collect,worker_root,worker_ssh}(755)`, `/opt/loop-openhands-agent/{agent_server_launcher.py,bin/codex-acp}`, `/usr/local/sbin/{loop-worker-volume,loop-worker-verify,loop-worker-seal}`, `/etc/loop-continuous/policy.json` (0600, ПЕРЕЗАПИШЕТ живой), sshd `97-loop-worker.conf`, sudoers, юниты volume/directories/agent-server | `enable+restart loop-worker-volume.service loop-openhands-directories.service loop-openhands-agent-server.service`; далее `wait_worker_api` + привязка Agent Profile `loop-codex` + `loop-worker-verify` (`install.py:767-771`) |

Нюансы apply:
- Файл считается изменённым при несовпадении sha256/mode/uid; запись атомарная (tmp+rename, `install.py:183-199`).
- Если `missing_private_or_runtime` непустой, install.py файлы положит, но сервисы НЕ будет включать/рестартовать: `status=installed_pending_private_inputs` (`install.py:762-766,783`). Для нашего релиза это значит: перед apply на хосте не должно быть пропавших приваток, иначе рестарт (и вход нового кода в строй) не случится.
- Worker: живые `/etc/loop-worker/templates.json` и `source-integrity.json` НЕ перезаписываются (пример кладётся только при отсутствии, `install.py:664-666`); templates.json входит в снапшот отката.
- Два прохода для worker (OPERATIONS.txt:140-143) актуальны только при пустом source-integrity; на живом claudette seal уже готов - один проход.
- При ошибке apply откат автоматический (файлы + состояния юнитов), см. §7.

Ручные (НЕ install.py) точки релиза:
- control: `/etc/loop/bridge.json` (поля `continuous_policy` - объект новой политики; `templates` - при необходимости), `/etc/loop-continuous/receiver.json` (поле `policy_fingerprint`), нативный оверрайд `/etc/loop/native/continuous_queue.py`.
- harper: `/etc/loop-runner/config.json` (поле `continuous_policy_fingerprint`; при необходимости `templates`).
- worker: `/etc/loop-continuous/receiver.json`, при необходимости `/etc/loop-worker/templates.json` + prompts + повторный seal.
- Все три: `/etc/loop-continuous/policy.json` обновит сам install.py (0600 root). Вручную не трогать, чтобы не разошлось с репо.

---

## 3. Порядок: control -> runner -> worker

Обоснование из кода: источник fingerprint - bridge на control (`ContinuousQueue(database, config["continuous_policy"])`, `bridge.py:106,970`; `continuous_queue.py:61`). Как только bridge перечитал новую политику, `/v1/queue` и все planning-пейлоады отдают `<NEW_FP>`; приёмники на старом fingerprint отвергнут регистрацию fail-closed (`continuous_receiver.py:77`), а admission-фенс сверит fingerprint очереди с регистрацией (`continuous_admission.py:45`). Пока очередь на паузе, ни того ни другого не происходит, поэтому окно между хостами безопасно. Порядок control -> runner -> worker закрывает отправителя первым и возвращат приёмники в строй последовательно.

Общее для всех шагов: на хосте обновить root-checkout релиза до релизного коммита (`git fetch && git checkout <release_sha>`), затем §5 шаг 0 уже выполнен (fingerprint записан).

### 3.1. Control (mckenzie)

```
# 1) бэкапы ручных точек
TS=$(date -u +%Y%m%dT%H%M%SZ)
sudo cp -a /etc/loop/bridge.json /etc/loop/bridge.json.before-v2-$TS
sudo cp -a /etc/loop-continuous/receiver.json /etc/loop-continuous/receiver.json.before-v2-$TS
sudo cp -a /etc/loop/native/continuous_queue.py /etc/loop/native/continuous_queue.py.before-v2-$TS

# 2) код + policy.json + юниты (авто-снапшот в /var/backups/loop-install)
sudo python3 infra/loop-control/install.py --role control --apply
```
3) Разобраться с `/opt/loop-control/compose.yaml`: apply перезапишет живой compose версией из репо. ПЕРЕД apply сравнить (`diff /opt/loop-control/compose.yaml <repo>/infra/loop-control/compose.yaml`): если в живом есть маунты нативных оверрайдов (`/etc/loop/native/...`), которых нет в репо - см. §8.1/§8.2, иначе рестарт compose может снять оверрайд.
4) Обновить `bridge.json`: заменить поле `continuous_policy` на объект политики wb-continuous-v2 (канонический JSON политики из репо). Сохранить uid 10001, mode 0600 (`install.py:633` проверяет). Править копией + `install -o 10001 -m 600` или `chown 10001: <tmp> && chmod 600 && mv`.
5) Обновить `receiver.json`: `policy_fingerprint = <NEW_FP>` (root 0600, nlink=1 - не делать hardlink, `continuous_receiver.py:95-97`).
6) Нативный оверрайд очереди - §4.
7) Рестарт bridge (минимальный, без bounce postgres/paperclip/hermes; install.py уже рестартовал loop-control.service - если compose не трогали вручную после этого, достаточно контейнера):
```
sudo docker restart loop-control-bridge-1
sudo systemctl restart loop-continuous.service   # прогон тика на новом коде, ранняя проверка
```
8) Проверка: `/v1/queue` -> `policy_fingerprint == <NEW_FP>`, `queue_paused == true`.

### 3.2. Runner (harper)

```
TS=$(date -u +%Y%m%dT%H%M%SZ)
sudo cp -a /etc/loop-runner/config.json /etc/loop-runner/config.json.before-v2-$TS
sudo python3 infra/loop-control/install.py --role runner --apply
```
Затем (осторожно: runner перечитывает config каждые 10 с; смена `continuous_policy_fingerprint` без reload-receipt валит цикл горячей перезагрузки fail-closed и останавливает опрос задач до рестарта, `runner.py:360-385,397-411`):
```
sudo systemctl stop loop-runner.service
# правка config.json: continuous_policy_fingerprint = <NEW_FP>  (owner verifier, 0600 - install.py:724)
sudo python3 - <<'PY'
import json,tempfile,os,shutil
p="/etc/loop-runner/config.json"
raw=open(p).read();cfg=json.loads(raw)
cfg["continuous_policy_fingerprint"]="NEW_FP"   # подставить реальный
tmp=tempfile.NamedTemporaryFile("w",dir="/etc/loop-runner",delete=False)
json.dump(cfg,tmp,sort_keys=True,indent=2);tmp.write("\n");tmp.flush();os.fsync(tmp.fileno());tmp.close()
shutil.copymode(p,tmp.name); os.chown(tmp.name,1000,1000)  # verifier
os.replace(tmp.name,p)
PY
sudo systemctl start loop-runner.service
```
Шаблоны: если в `config.json.templates` остались шаблоны со старым base_sha и политика v2 переиспользует те же имена шаблонов - новая регистрация с тем же именем упадёт «template registration conflict» (`continuous_register.py:101-102`). Решение до релиза: новые имена шаблонов в v2, либо убрать старые записи в то же окно (бэкап уже снят), либо идти потоком advance_base с `rebase_templates` (§5, примечание).

### 3.3. Worker (claudette)

```
TS=$(date -u +%Y%m%dT%H%M%SZ)
sudo cp -a /etc/loop-continuous/receiver.json /etc/loop-continuous/receiver.json.before-v2-$TS
sudo python3 infra/loop-control/install.py --role worker --apply
```
Затем:
- `receiver.json`: `policy_fingerprint = <NEW_FP>` (root 0600).
- Если v2 меняет промпты/шаблоны: обновить `/etc/loop-worker/templates.json` (+ промпты в `/etc/loop-worker/prompts`), затем обязательный повторный seal `sudo /usr/local/sbin/loop-worker-seal` (промпты входят в sealed-манифест, `seal_worker_integrity.py`, `install.py:367-388`), затем `sudo /usr/local/sbin/loop-worker-verify`.
- Отдельного рестарта демона не требуется: receiver и dispatch - процессы на invocation (forced-SSH, `worker_ssh.py`); install.py уже рестартовал agent-server. Если templates.json менялся - планировщик dispatcher на harper читает его по SSH на каждый dispatch, новая копия подхватится сама.

---

## 4. Нативный оверрайд continuous_queue.py (control)

Факт живой системы: контейнер `loop-control-bridge-1` монтирует `/etc/loop/native/continuous_queue.py` поверх `/opt/loop/continuous_queue.py`. В репо на `server/loop-continuous` такого маунта в `compose.yaml` НЕТ (bridge собирается из `Dockerfile.bridge`, который COPY-ит код в образ, и volumes ограничены `bridge.json`, `openhands_relay.py`, secrets) - значит живой compose отличается от репо либо маунт добавлен вручную. Отсюда правило:

1. Обновить ОБА файла одним контентом из релизного чекаута:
```
sudo install -o root -g root -m 644 infra/loop-control/../../tools/loop/continuous_queue.py /opt/loop/continuous_queue.py   # install.py делает это сам
sudo install -o root -g root -m 644 tools/loop/continuous_queue.py /etc/loop/native/continuous_queue.py                   # ручной шаг
```
(install.py кладёт только `/opt/loop/...`; `/etc/loop/native/...` - всегда ручной шаг, он НЕ в CONTROL_RUNTIME_FILES).
2. Проверить до/после: `sudo docker inspect loop-control-bridge-1 --format '{{json .Mounts}}' | python3 -m json.tool` - убедиться, что маунт нативного файла жив и после рестарта.
3. Рестарт контейнера после обновления обоих файлов и bridge.json: `sudo docker restart loop-control-bridge-1` (python читает код и `continuous_policy` при старте процесса).
4. Если в живом compose оверрайд сделан через `docker-compose.override.yaml`/правку `/opt/loop-control/compose.yaml` - зафиксировать это в репо отдельным PR, иначе следующий `install.py --role control --apply` + bounce `loop-control.service` соберёт контейнер по репо-версии без оверрайда (см. §8.2).

---

## 5. Синхронизация policy_fingerprint (точные файлы и поля)

Код, который читает/проверяет fingerprint:
- Отправитель: `bridge.json -> "continuous_policy"` (объект) -> `digest(validate_policy(...))` (`continuous_queue.py:12,61`); наружу через `GET /v1/queue -> policy_fingerprint`.
- Приёмники (все три): `/etc/loop-continuous/receiver.json` -> поля строго `{role, policy_fingerprint, policy_file, lock_file}`, `policy_file=/etc/loop-continuous/policy.json`, `lock_file=/etc/loop-continuous/receiver.lock` (`continuous_receiver.py:97-98`). При регистрации требуется тройное совпадение: `registration.policy_fingerprint == receiver.json.policy_fingerprint`, `digest(/etc/loop-continuous/policy.json) == receiver.json.policy_fingerprint`, registration внутри pinned policy (`continuous_receiver.py:77-82`).
- harper дополнительно: `/etc/loop-runner/config.json -> "continuous_policy_fingerprint"`; consumed при старте (`runner.py:393-396`) и в hot-reload каждые 10 с (`runner.py:400-403`).
- worker: sidecar каждой попытки несёт `policy_fingerprint`, сверяется с `digest(/etc/loop-continuous/policy.json)` (`worker_prompt.py:28-51`); receiver-worker сверяет feedback-sidecar со своим `receiver.json.policy_fingerprint` (`continuous_receiver.py:52`).

Таблица синхронизации (все поля = `<NEW_FP>` или объект политики v2):

| Хост | Файл | Поле | Кто обновляет | Права |
|---|---|---|---|---|
| mckenzie | `/etc/loop/bridge.json` | `continuous_policy` (объект политики v2 целиком) | вручную | uid 10001, 0600 |
| mckenzie | `/etc/loop-continuous/policy.json` | контент политики v2 | install.py (control apply) | root, 0600 |
| mckenzie | `/etc/loop-continuous/receiver.json` | `policy_fingerprint` | вручную | root, 0600 |
| harper | `/etc/loop-continuous/policy.json` | контент | install.py (runner apply) | root, 0600 |
| harper | `/etc/loop-continuous/receiver.json` | `policy_fingerprint` | вручную | root, 0600 |
| harper | `/etc/loop-runner/config.json` | `continuous_policy_fingerprint` | вручную | verifier(1000), 0600 |
| claudette | `/etc/loop-continuous/policy.json` | контент | install.py (worker apply) | root, 0600 |
| claudette | `/etc/loop-continuous/receiver.json` | `policy_fingerprint` | вручную | root, 0600 |

Контрольное вычисление на каждом хосте:
```
sudo python3 -c 'import json,sys; sys.path.insert(0,"/opt/loop"); from continuous_queue import digest; print(digest(json.load(open("/etc/loop-continuous/policy.json"))))'
```
Ожидаемо `<NEW_FP>` на всех трёх, и то же значение в receiver.json (bridge/harper/worker) и в config.json harper.

Примечание (advance_base): в коде есть штатный in-band механизм ротации политики+базы - `tools/loop/continuous_base_refresh.py` (maintenance_key, git-bundle, merge_commits, migration manifest, журналы на каждом приёмнике, reload-receipt/ack на harper; пишет ровно те же файлы: policy.json, receiver.json, роль-конфиг, `bridge.json.continuous_policy`/`config.json.continuous_policy_fingerprint`, `continuous_base_refresh.py:239-303`). Если политика v2 подготовлена как advance_base-пейлоад (есть maintenance journal) - использовать его вместо ручных правок §3/§5: он атомарен, делает бэкапы `.base-refresh-backup` и ребейзит застрявшие элементы очереди. Ручной путь выше - его зеркало без bundle-машинерии.

---

## 6. Верификация после деплоя

По порядку на каждом хосте:
```
sudo python3 infra/loop-control/install.py --role control --check   # на mckenzie -> "status": "ready", public_drift []
sudo python3 infra/loop-control/install.py --role runner --check    # на harper
sudo python3 infra/loop-control/install.py --role worker --check    # на claudette
```
(`--check` по чистому хосту дополнительно проверяет worker-profile binding и `loop-worker-verify`, `install.py:772-776`.)

Control (mckenzie):
```
TOKEN=$(sudo cat /etc/loop/secrets/bridge_operator)
curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:18770/v1/queue
#  -> policy_fingerprint == <NEW_FP>; queue_paused == true (пока держим паузу)
sudo journalctl -u loop-continuous.service -n 50 --no-pager
#  тик на новом коде: на паузе ожидаем {"status":"paused", ...} без трейсбеков
```
Fingerprint-консистентность: контрольная команда из §5 на всех трёх хостах + `receiver.json` и `config.json` показывают `<NEW_FP>`.

Runner (harper):
```
systemctl is-active loop-runner.service loop-runner-bridge-tunnel.service
sudo journalctl -u loop-runner.service -n 50 --no-pager   # старт без "installed runner config differs..." / без цикла ошибок reload
```

Worker (claudette): `sudo /usr/local/sbin/loop-worker-verify` (запускается и самим install.py), статус `loop-openhands-agent-server.service`.

Разпауза и сквозной тик (когда все три зелёные):
```
curl -sS -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:18770/v1/resume
# через <=5 мин (loop-continuous.timer):
curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:18770/v1/queue
#  -> queue_paused == false; далее тик сам дёрнет POST /v1/queue/plan (continuous_tick.py:95-103)
#  -> ожидать появление items с policy_fingerprint == <NEW_FP>, state proposed -> registering -> ready
sudo journalctl -u loop-continuous.service -f   # status "ok"/"planning_started", dispatch/admission без blockers
```
Планирование нового slice: первый тик после разпаузы создаёт план под `<NEW_FP>` (planning_key включает policy fingerprint, `continuous_tick.py:27-31`); при задержке проверить `plan_exhausted`/`planning_retry_exhausted` в статусе.

---

## 7. Откат

Слои бэкапов:
- Ручные: `<файл>.before-v2-<TS>` рядом с каждым правленым файлом (bridge.json, receiver.json x2, config.json, нативный continuous_queue.py, templates.json если трогали).
- install.py: `/var/backups/loop-install/<штамп>-<pid>/manifest.json` + `.bak` по каждому таргету + states юнитов (каждый apply создаёт новый каталог; не удалять до закрытия релиза).

Порядок отката (обратный деплою, вся процедура - снова одно окно при паузе):
1. Пауза: `POST /v1/pause` (если успели разпаузить). Дождаться отсутствия `current`/active planning в `/v1/queue`.
2. Control: вернуть `/etc/loop/bridge.json` (`continuous_policy` v1) и `/etc/loop-continuous/receiver.json` (91df66f6...) из `.before-v2-*`; вернуть `/etc/loop/native/continuous_queue.py`; затем:
   - предпочтительно: `cd <release-checkout на ПРЕДЫДУЩИЙ коммит> && sudo python3 infra/loop-control/install.py --role control --apply` (откатит все публичные файлы по своему словарю);
   - либо точечно из манифеста: `sudo python3` + `restore_snapshot(manifest.json)`-эквивалент (файлы из `/var/backups/loop-install/...`) и `sudo docker restart loop-control-bridge-1`.
3. Runner: из `.before-v2-*` вернуть `/etc/loop-runner/config.json` (`continuous_policy_fingerprint` 91df66f6...); install.py предыдущего коммита `--role runner --apply` откатит код; он сам рестартует `loop-runner.service` (либо вручную `systemctl restart loop-runner.service`).
4. Worker: вернуть `receiver.json` (91df66f6...); install.py предыдущего коммита `--role worker --apply`; если менялись templates/prompts - вернуть их и повторить `loop-worker-seal`, затем `loop-worker-verify`.
5. Контроль отката: `/v1/queue` снова `policy_fingerprint == 91df66f6...`; три `install.py --check` = ready.
6. Если между хостами уже разъехалось (registration отклонялась) - ничего дополнительно чистить не надо: отклонённые регистрации не мутируют конфиги приёмников (fail closed до install()).
7. Авто-откат install.py: если сам apply упал с ошибкой - он уже вернул файлы и юниты (restore_snapshot + restore_units, `install.py:777-782`); вручную докатить только ручные точки (bridge.json/receiver.json/config.json), если их успели изменить после apply.

Элементы очереди, ушедшие в «заморозку» по старому/новому fingerprint (§1.2), при откате снова становятся видимы своему fingerprint - список ID из §1.2 сверить.

---

## 8. НЕ УВЕРЕН - проверить оператору на живых хостах

1. **Как bridge.py попадает в живой контейнер.** В репо `compose.yaml` маунтов `/opt/loop/*.py` в контейнер bridge нет - код запечён в digest-pinned образ (`Dockerfile.bridge` COPY). Если на mckenzie `docker inspect loop-control-bridge-1` не покажет маунт и для `bridge.py` (в отличие от `continuous_queue.py`), то обновление `/opt/loop/bridge.py` на хосте НИЧЕГО не меняет до пересборки образа на Harper и обновления дайджеста в `/etc/loop/images.env` + `compose up`. Проверить маунты до деплоя и решить: rebuild image или временный host-mount.
2. **Живой `/opt/loop-control/compose.yaml` vs репо.** `install.py --role control --apply` перезапишет живой compose репо-версией; если в живом добавлены маунты нативных оверрайдов (`/etc/loop/native/continuous_queue.py` - точно, возможно и `bridge.py`), рестарт `loop-control.service`/`compose up` после apply их СНИМЕТ. Нужен diff живого vs репо и, если различие реально, сначала PR с оверрайдами в репо (либо исключить compose из apply на время релиза - но тогда `--check` вечно будет показывать drift).
3. **Путь install-checkout на harper и claudette.** Откуда оператор запускает `install.py` (root-owned checkout релизного коммита) на runner и worker - в коде/доках не зафиксировано; `/srv/loop-runner/source/proxima-ai` - рабочий checkout verifier-а, использовать его как источник инсталла без проверки прав/владельца не уверен. Проверить владельца и выбрать отдельный root-checkout.
4. **Судьба зарегистрированных шаблонов со старым base_sha.** Если v2 переиспользует имена шаблонов v1, первая же регистрация упадёт «template registration conflict» на всех трёх конфигах (`continuous_register.py:101-102`), а worker-проверки (validate_worker_integrity/`worker_prompt`) ждут sealed-промпты. Проверить список templates в `bridge.json`, `/etc/loop-runner/config.json`, `/etc/loop-worker/templates.json` и решить: новые имена в v2 / удаление старых записей в окне / полный поток advance_base.
5. **Замороженные элементы очереди.** Точный список недошедших items по 91df66f6... и решение по ним (drain до релиза vs принять заморозку) - проверить `/v1/queue` перед началом; восстановить их можно только потоком advance_base (`rebase_templates`), вручную - нет.
