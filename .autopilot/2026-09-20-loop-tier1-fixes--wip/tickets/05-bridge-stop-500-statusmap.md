# T05 — R05+R06+R07: bridge stop-wedge + 500/traceback + единая статус-мэпа

**Требования:** R05, R06, R07 · **Зона:** tools/loop, tools/tests · **Волна:** 1 · **Status:** ready

## Что должно заработать

/stop по childless paperclip подтверждается по upstream-TERMINAL и больше не крутится в «cancelling»; повторный /stop идемпотентен; сбой внутри bridge отдаёт 500+uncertain с traceback в stderr; serve-цикл runner'а не глотает исключения.

## Критерии приёмки

- [ ] _cancel: ранний возврат при state=cancelled (без регресса в cancelling)
- [ ] paperclip: POST cancel → GET → PAPERCLIP_STATUS_MAP → stop_ok по TERMINAL
- [ ] PAPERCLIP_STATUS_MAP одна на reconcile и fence
- [ ] handler: не-BridgeError → traceback + 500 {uncertain:true}; silencer снят
- [ ] runner serve: traceback в except
- [ ] pytest test_loop_bridge.py зелёный (новые кейсы R05, R06)

## Прогон

- [x] реализовано
- [x] тест
- [x] ревью
