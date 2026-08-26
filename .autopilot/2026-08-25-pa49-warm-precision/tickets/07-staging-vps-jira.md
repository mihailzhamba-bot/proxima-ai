# 07 — Staging на VPS через SSH-туннель + Jira PA-49

**Требования:** G01, G01.1, R12, R13i, G-GIT-1
**Blocked by:** 06
**Зона:** VPS (staging-контейнер), `~/.ssh/config` Mike (алиас proxima-app), Jira PA-49
**Волна:** 5
**Status:** ready

## Что должно заработать

Кабинет открывается с любой машины Mike: webapp собран и запущен на VPS как staging-контейнер `proxima-webapp-staging` (порт опубликован ТОЛЬКО на 127.0.0.1 VPS:3000, restart: unless-stopped, env WEBAPP_REQUIRE_AUTH=false - fixtures-режим без БД и секретов). SSH-алиас `proxima-app` на машине Mike (LocalForward 3000). Публичные порты 80/443 НЕ открываются, Caddy/домен не трогаются. После проверки - комментарий в Jira PA-49 (без смены статуса): что сделано, ветка, как посмотреть.

## Из брифа, дословно

> «Staging на VPS через туннель» — webapp на VPS как staging-контейнер за SSH-туннелем, без домена/80/443; переключение на публичный URL позже

## Разделы спецификации

Истории 15, 16, 24, 14; Решения «Staging»; паттерн PA-13 (git bundle → detached checkout → docker build на VPS).

## Критерии приёмки

- [ ] На VPS: образ собран из ветки (git bundle, паттерн PA-13), контейнер proxima-webapp-staging работает, restart: unless-stopped
- [ ] Порт 3000 published только на 127.0.0.1 VPS (проверка: ss/netstat - извне недоступен)
- [ ] SSH-алиас proxima-app добавлен в ~/.ssh/config Mike (с предупреждением в отчёте); туннель -> http://localhost:3000 открывает бриф
- [ ] Основной compose-стек VPS (postgres и т.д.) не тронут; 80/443 закрыты
- [ ] Jira PA-49: комментарий с итогом, веткой, инструкцией просмотра; статус НЕ менялся
- [ ] Ветки/коммиты: атомарные коммиты на feat/pa-49-warm-precision, в main не коммитили, чужие файлы не стейджились
