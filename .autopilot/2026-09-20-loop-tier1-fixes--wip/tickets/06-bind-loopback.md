# T06 — R08: bind по умолчанию loopback + OPERATIONS.txt

**Требования:** R08 · **Зона:** infra/loop-control · **Волна:** 1 · **Status:** ready

## Что должно заработать

Пример конфига моста по умолчанию слушает loopback; оператор ExplicitDecision для не-loopback bind с TLS-фронтом задокументирован.

## Критерии приёмки

- [ ] bridge.config.example.json: bind 127.0.0.1
- [ ] OPERATIONS.txt: абзац про сетевой доступ моста (правка существующего файла)
- [ ] pytest test_loop_config.py зелёный (bind не ассертится)

## Прогон

- [x] реализовано
- [x] тест
- [x] ревью
