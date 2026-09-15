"""Hermes native Telegram extension. Trusted commands never pass through the LLM.

Installed as a read-only user plugin. Model-visible tools have a separate
read/draft credential. The pre-dispatch hook validates native event provenance
itself because Hermes calls that hook before its own authorization.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, "/opt/loop")
try:
    from .bridge import JsonHTTP, secret, BridgeError
    from .chat_tool import TOOLS
except ImportError:
    from bridge import JsonHTTP, secret, BridgeError
    from chat_tool import TOOLS

PENDING = set()
CONTROLS = {"loop_status", "loop_review", "loop_confirm", "loop_stop"}
SAFE_NATIVE = {"start", "help", "new", "reset"}


def value(item):
    return str(getattr(item, "value", item))


def authorized(event, config):
    source = event.source
    user, chat = str(config.get("user_id", "")), str(config.get("chat_id", ""))
    return (bool(re.fullmatch(r"[1-9][0-9]{0,19}", user)) and user == chat
            and value(source.platform) == "telegram" and value(source.chat_type) == "dm"
            and str(source.user_id) == user and str(source.chat_id) == chat
            and not getattr(source, "is_bot", False)
            and not getattr(source, "delivered_via_upstream_relay", False)
            and not getattr(event, "internal", False)
            and getattr(event, "allow_gateway_control", False) is True)


def owner_payload(event):
    return {"user_id": str(event.source.user_id), "chat_id": str(event.source.chat_id),
            "chat_type": value(event.source.chat_type)}


def status_text(result):
    paused = "на паузе" if result["queue_paused"] else "принимает задания"
    lines = [f"Очередь LOOP: {paused}. Director: {result['director_status']}.",
             "Результат разработки - PR. Независимое ревью пока требует оператора."]
    jobs = result.get("jobs", [])[:5]
    if not jobs:
        lines.append("Сохранённых задач пока нет.")
    for job in jobs:
        lines.append(f"{job['id']}: {job['state']}" + (f"\n{job['pr_url']}" if job.get("pr_url") else ""))
    lines.append("Это сохранённые состояния задач; ежедневный WB-пилот ещё не принят.")
    deliveries = result.get("notification_deliveries", {})
    if deliveries.get("delivery_unknown"):
        lines.append(f"Есть уведомления с неподтверждённой доставкой: {deliveries['delivery_unknown']}. Результаты задач проверяйте по статусам выше.")
    return "\n".join(lines)


def preview_text(result):
    return ("Подтверждение фиксированного задания LOOP\n"
            f"Изменение: {result['description']}\n"
            f"Ожидаемый результат: {result['expected_result']}\n"
            f"Шаблон: {result['template']}\n"
            f"Задача: {result['job_id']}\n"
            f"Исходный commit: {result['base_sha']}\n"
            "Разрешённые файлы:\n" + "\n".join(result["allowed_paths"]) +
            "\nРезультат: проверенный PR. Merge и production deploy не выполняются."
            "\nДля запуска отправьте отдельным сообщением:\n" + result["confirm_command"])


class NativePlugin:
    def __init__(self, config):
        self.config = config

    def client(self, role):
        return JsonHTTP(self.config["bridge_url"], secret(self.config[role + "_token_file"]),
                        timeout=20, trusted_bridge=True)

    def model_call(self, name, args):
        # ContextVars are supplied by the native gateway, never tool arguments.
        from gateway.session_context import get_session_env
        identity = {key: get_session_env("HERMES_SESSION_" + key) for key in ("PLATFORM", "USER_ID", "CHAT_ID", "CHAT_TYPE")}
        if (identity["PLATFORM"] != "telegram" or identity["CHAT_TYPE"] != "dm"
                or str(identity["USER_ID"]) != str(self.config.get("user_id"))
                or str(identity["CHAT_ID"]) != str(self.config.get("chat_id"))):
            return json.dumps({"error": "native owner conversation required"})
        try:
            if name == "loop_get_status" and args == {}:
                result = self.client("chat").call("GET", "/v1/chat/status")
            elif name == "loop_prepare_action" and isinstance(args, dict) and set(args) == {"template"}:
                result = self.client("chat").call("POST", "/v1/chat/drafts", args)
            else:
                raise ValueError()
            return json.dumps(result, ensure_ascii=False)
        except Exception:
            return json.dumps({"error": "LOOP unavailable; no execution confirmed"})

    async def handle(self, gateway, source, command, args, actor):
        try:
            if command == "loop_status":
                result = await asyncio.to_thread(self.client("chat").call, "GET", "/v1/chat/status")
                text = status_text(result)
            elif command in {"loop_review", "loop_confirm"}:
                if not re.fullmatch(r"[a-f0-9-]{36}", args):
                    raise ValueError()
                route = "preview" if command == "loop_review" else "confirm"
                result = await asyncio.to_thread(self.client("ingress").call, "POST", "/v1/native/" + route,
                                                 {**actor, "draft_id": args})
                if route == "preview":
                    sent = await gateway._adapter_for_source(source).send(source.chat_id, preview_text(result))
                    if getattr(sent, "success", False) and getattr(sent, "message_id", None):
                        await asyncio.to_thread(self.client("ingress").call, "POST", "/v1/native/preview-receipt",
                                                {**actor, "draft_id": args, "preview_nonce": result["preview_nonce"],
                                                 "message_id": str(sent.message_id)})
                    return
                text = preview_text(result) if route == "preview" else (
                    f"Запуск: {result['run_id']}. Статус: {result['status']}."
                    "\nЭто состояние управляющего запуска, не подтверждение готового PR. Проверка: /loop_status")
            elif command == "loop_stop":
                if not re.fullmatch(r"[a-f0-9-]{36}", args):
                    raise ValueError()
                result = await asyncio.to_thread(self.client("ingress").call, "POST", "/v1/native/stop",
                                                 {**actor, "run_id": args})
                text = ("Остановка подтверждена." if result.get("status") == "cancelled" else
                        "Остановка запрошена, но ещё не подтверждена. Статус: " + str(result.get("status")))
                if result.get("reason") == "ready_pr_exists":
                    text = "PR уже создан; выполненная публикация не отменена."
            else:
                text = "Эта команда управления Hermes отключена для Director. Пишите обычным текстом или используйте /loop_status."
        except BridgeError as exc:
            text = ("Результат запроса неизвестен. Не создавайте новую такую же задачу; проверьте /loop_status." if exc.uncertain else
                    "Команда не выполнена. Проверьте паузу очереди и Director; подтверждение запуска требует свежего /loop_review ID.")
        except Exception:
            text = "Команда недоступна или указан неверный ID. Новая работа не подтверждена. Проверка: /loop_status."
        try:
            adapter = gateway._adapter_for_source(source)
            await adapter.send(source.chat_id, text)
        except Exception:
            # Do not log transport exceptions: bot URLs contain credentials.
            pass

    async def notify(self):
        # Version-coupled native accessor is also used by Hermes platform_actions.
        # Durable claim-before-send prevents an ambiguous delivery from being resent.
        while True:
            try:
                if not self.config.get("user_id"):
                    await asyncio.sleep(30)
                    continue
                from gateway.run import _gateway_runner_ref
                from gateway.config import Platform
                from gateway.session import SessionSource
                gateway = _gateway_runner_ref() if _gateway_runner_ref else None
                source = SessionSource(platform=Platform.TELEGRAM, chat_id=str(self.config['chat_id']),
                                       chat_type='dm', user_id=str(self.config['user_id']))
                adapter = gateway._adapter_for_source(source) if gateway else None
                if adapter is not None:
                    client = self.client("ingress")
                    result = await asyncio.to_thread(client.call, "GET", "/v1/native/notifications")
                    for item in result["pending"]:
                        path = "/v1/native/notifications/" + item["id"]
                        receipt = await asyncio.to_thread(client.call, "POST", path + "/claim", {})
                        delivered = False
                        try:
                            sent = await adapter.send(source.chat_id, receipt["text"])
                            delivered = bool(getattr(sent, "success", False))
                        finally:
                            await asyncio.to_thread(client.call, "POST", path + "/settle", {"delivered": delivered})
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(30)

    def gate(self, event, gateway, session_store=None):
        try:
            if value(event.source.platform) != "telegram":
                return None
            if not authorized(event, self.config):
                return {"action": "skip", "reason": "loop-native-owner-only"}
            text = str(getattr(event, "text", "") or "").strip()
            if not text.startswith("/"):
                return None
            parts = text.split(maxsplit=1)
            command = parts[0][1:].split("@", 1)[0].replace("-", "_").lower()
            if command in SAFE_NATIVE:
                return None
            if len(PENDING) < 8:
                task = asyncio.create_task(self.handle(gateway, event.source, command,
                                                       parts[1].strip() if len(parts) > 1 else "",
                                                       owner_payload(event)))
                PENDING.add(task)
                task.add_done_callback(PENDING.discard)
            return {"action": "skip", "reason": "loop-native-command"}
        except Exception:
            return {"action": "skip", "reason": "loop-native-rejected"}


def register(ctx):
    try:
        config = json.loads(Path(os.environ.get("LOOP_NATIVE_CONFIG", "/etc/loop/native-telegram.json")).read_text())
    except Exception:
        config = {}  # Fail closed for every Telegram event until configured.
    plugin = NativePlugin(config)
    ctx.register_hook("pre_gateway_dispatch", plugin.gate)
    for name in CONTROLS:
        ctx.register_command(name.replace("_", "-"), lambda raw_args: "Native LOOP ingress unavailable; nothing executed.",
                             description="Управление LOOP из личного Telegram-чата")
    for tool in TOOLS:
        name = tool["name"]
        ctx.register_tool(name=name, toolset="loop_chat",
                          schema={"name": name, "description": tool["description"], "parameters": tool["inputSchema"]},
                          handler=lambda args, name=name: plugin.model_call(name, args))
