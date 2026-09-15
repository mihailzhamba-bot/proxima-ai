"""Native Hermes chat controls. Model drafts are not owner authorization.

Only the native ingress credential may preview/confirm/stop; the MCP credential
can read sanitized state and draft a fixed admitted template. No free-form task
text is forwarded to the execution lane.
"""
from __future__ import annotations

import json
import hashlib
import re
import threading
import time
import uuid
from urllib.parse import quote

try:
    from .bridge import BridgeError, template_fingerprint
except ImportError:
    from bridge import BridgeError, template_fingerprint


class NativeControl:
    def __init__(self, bridge, config):
        self.bridge = bridge
        bridge.require_parent_for_jobs = True
        self.config = config
        self.settings = config.get("native_telegram", {})
        self.lock = threading.RLock()
        with bridge.tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS native_drafts (
                id TEXT PRIMARY KEY, template TEXT NOT NULL, fingerprint TEXT NOT NULL,
                user_id TEXT NOT NULL, chat_id TEXT NOT NULL, created REAL NOT NULL,
                state TEXT NOT NULL DEFAULT 'draft', previewed REAL,
                run_id TEXT, error TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS native_notifications (
                id TEXT PRIMARY KEY, text TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
                created REAL NOT NULL)""")
            db.execute("UPDATE native_notifications SET state='delivery_unknown' WHERE state='sending'")
            columns = {r[1] for r in db.execute("PRAGMA table_info(native_drafts)")}
            for column in ("preview_nonce", "preview_message"):
                if column not in columns:
                    db.execute(f"ALTER TABLE native_drafts ADD COLUMN {column} TEXT")
            notification_columns = {r[1] for r in db.execute("PRAGMA table_info(native_notifications)")}
            if "claimed_at" not in notification_columns:
                db.execute("ALTER TABLE native_notifications ADD COLUMN claimed_at REAL")

    def owner(self, payload):
        user = str(self.settings.get("user_id", ""))
        chat = str(self.settings.get("chat_id", ""))
        if not re.fullmatch(r"[1-9][0-9]{0,19}", user) or user != chat:
            raise BridgeError(503, "native private chat is not configured", False)
        if str(payload.get("user_id", "")) != user or str(payload.get("chat_id", "")) != chat:
            raise BridgeError(403, "private owner chat required", False)
        if payload.get("chat_type") != "dm":
            raise BridgeError(403, "private owner chat required", False)
        return user, chat

    def templates(self):
        names = self.settings.get("templates", [])
        return {name: self.config.get("templates", {})[name] for name in names
                if name in self.config.get("templates", {})}

    def contract(self, name):
        description = self.settings.get("descriptions", {}).get(name, {})
        if not all(isinstance(description.get(k), str) and 0 < len(description[k]) <= 2000
                   for k in ("description", "expected_result")):
            raise BridgeError(503, "trusted template description missing", False)
        definition = self.templates()[name]
        body = {"template_fingerprint": template_fingerprint(name, definition),
                "description": description["description"], "expected_result": description["expected_result"]}
        return {**body, "fingerprint": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()}

    def status(self):
        with self.bridge.tx() as db:
            self.expire_delivery_claims(db)
            paused = db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == "true"
            jobs = [dict(r) for r in db.execute("""SELECT j.id,j.state,j.pr_url,j.director_run,
                j.candidate_sha,o.updated FROM jobs j JOIN operations o ON o.id=j.director_run
                ORDER BY o.created DESC,j.id DESC LIMIT 10""")]
            runs = [dict(r) for r in db.execute("""SELECT id,kind,state,created,updated
                FROM operations WHERE kind='paperclip' ORDER BY created DESC LIMIT 10""")]
            deliveries = {r["state"]: r["count"] for r in db.execute(
                "SELECT state,count(*) AS count FROM native_notifications GROUP BY state")}
        director = "unknown"
        try:
            agent = self.bridge.paperclip.call("GET", "/api/agents/" + quote(self.bridge.director_id, safe=""))
            director = agent.get("status", "unknown")
        except BridgeError:
            pass
        return {"mode": "pr_only", "queue_paused": paused, "director_status": director,
                "observed_at": time.time(), "runs": runs, "jobs": jobs,
                "templates": list(self.templates()), "job_status_source": "persistent_bridge_state",
                "daily_wb_accepted": False,
                "notification_deliveries": deliveries,
                "review_mode": "independent_operator_receipt_required"}

    def draft(self, payload):
        if set(payload) != {"template"} or payload.get("template") not in self.templates():
            raise BridgeError(400, "choose an admitted template; arbitrary development is not enabled", False)
        user, chat = self.owner({"user_id": self.settings.get("user_id"),
                                 "chat_id": self.settings.get("chat_id"), "chat_type": "dm"})
        name = payload["template"]
        fingerprint = self.contract(name)["fingerprint"]
        with self.bridge.tx() as db:
            # Repeated model calls do not flood the chat with equivalent drafts.
            old = db.execute("""SELECT id FROM native_drafts WHERE template=? AND fingerprint=?
                AND user_id=? AND chat_id=? AND state='draft' AND created>? ORDER BY created DESC LIMIT 1""",
                (name, fingerprint, user, chat, time.time() - 900)).fetchone()
            draft_id = old["id"] if old else str(uuid.uuid4())
            if not old:
                db.execute("INSERT INTO native_drafts(id,template,fingerprint,user_id,chat_id,created) VALUES(?,?,?,?,?,?)",
                           (draft_id, name, fingerprint, user, chat, time.time()))
        return {"draft_id": draft_id, "state": "awaiting_owner_review",
                "next_command": "/loop_review " + draft_id,
                "notice": "No execution started. Owner must view the trusted preview and explicitly confirm."}

    def get_draft(self, draft_id):
        with self.bridge.tx() as db:
            row = db.execute("SELECT * FROM native_drafts WHERE id=?", (draft_id,)).fetchone()
        if not row:
            raise BridgeError(404, "draft unavailable", False)
        return dict(row)

    def validate_draft(self, draft, owner):
        if (draft["user_id"], draft["chat_id"]) != owner:
            raise BridgeError(403, "draft belongs to another chat", False)
        if draft["template"] not in self.templates() or self.contract(draft["template"])["fingerprint"] != draft["fingerprint"]:
            raise BridgeError(409, "template changed; request a new draft", False)
        if time.time() - draft["created"] > 900:
            raise BridgeError(409, "draft expired; request a new draft", False)

    def preview(self, payload):
        owner = self.owner(payload)
        draft = self.get_draft(payload.get("draft_id"))
        self.validate_draft(draft, owner)
        if draft["state"] != "draft":
            raise BridgeError(409, "draft already consumed; inspect current status", False)
        definition = self.templates()[draft["template"]]
        contract = self.contract(draft["template"])
        nonce = str(uuid.uuid4())
        with self.bridge.tx() as db:
            db.execute("UPDATE native_drafts SET preview_nonce=?,previewed=NULL,preview_message=NULL WHERE id=? AND state='draft'",
                       (nonce, draft["id"]))
        return {"draft_id": draft["id"], "template": draft["template"],
                "description": contract["description"], "expected_result": contract["expected_result"],
                "preview_nonce": nonce,
                "base_sha": definition["base_sha"], "allowed_paths": definition["allowed_paths"],
                "fingerprint": draft["fingerprint"], "mode": "pr_only",
                "job_id": "tg-" + draft["id"].replace("-", ""),
                "expires_at": draft["created"] + 900,
                "confirm_command": "/loop_confirm " + draft["id"]}

    def preview_receipt(self, payload):
        owner = self.owner(payload)
        draft = self.get_draft(payload.get("draft_id"))
        self.validate_draft(draft, owner)
        message = str(payload.get("message_id", ""))
        if not re.fullmatch(r"[1-9][0-9]{0,19}", message) or not payload.get("preview_nonce"):
            raise BridgeError(400, "successful Telegram delivery receipt required", False)
        with self.bridge.tx() as db:
            changed = db.execute("""UPDATE native_drafts SET previewed=?,preview_message=?
                WHERE id=? AND state='draft' AND preview_nonce=?""",
                (time.time(), message, draft["id"], payload["preview_nonce"])).rowcount
        if not changed:
            raise BridgeError(409, "preview superseded or already consumed", False)
        return {"preview_delivered": True}

    def confirm(self, payload):
        owner = self.owner(payload)
        with self.lock:
            draft = self.get_draft(payload.get("draft_id"))
            if (draft["user_id"], draft["chat_id"]) != owner:
                raise BridgeError(403, "draft belongs to another chat", False)
            key = "native-telegram-" + draft["id"]
            # Read existing intent before expiry/config checks: a repeat is a lookup.
            with self.bridge.tx() as db:
                op = db.execute("SELECT id,state FROM operations WHERE kind='paperclip' AND key=?", (key,)).fetchone()
            if op:
                return {"run_id": op["id"], "status": op["state"], "duplicate": True}
            if draft["state"] != "draft":
                raise BridgeError(409, "dispatch outcome unknown; operator reconciliation required", True)
            self.validate_draft(draft, owner)
            if not draft["previewed"]:
                raise BridgeError(409, "view /loop_review before confirming", False)
            state = self.status()
            if state["queue_paused"] or state["director_status"] not in {"idle", "running"}:
                raise BridgeError(409, "execution is paused or unavailable; chat remains available", False)
            with self.bridge.tx() as db:
                db.execute("UPDATE native_drafts SET state='dispatching' WHERE id=?", (draft["id"],))
            execution = {"source": "native_telegram", "draft_id": draft["id"],
                         "template": draft["template"], "template_fingerprint": self.contract(draft["template"])["template_fingerprint"],
                         "approval_fingerprint": draft["fingerprint"],
                         "job_id": "tg-" + draft["id"].replace("-", ""),
                         "goal": "Execute only the owner-confirmed fixed template. Propose exactly this job_id and template using your trusted run_id and generation. Stop after proposal; the runner owns verification and PR publication."}
            try:
                result = self.bridge.create("paperclip", key, execution)
            except BridgeError as exc:
                with self.bridge.tx() as db:
                    db.execute("UPDATE native_drafts SET state=?,error=? WHERE id=?",
                               ("unknown" if exc.uncertain else "rejected", exc.message, draft["id"]))
                raise
            with self.bridge.tx() as db:
                db.execute("UPDATE native_drafts SET state='submitted',run_id=? WHERE id=?",
                           (result["run_id"], draft["id"]))
            return result

    def stop(self, payload):
        self.owner(payload)
        run_id = payload.get("run_id")
        try:
            if str(uuid.UUID(run_id)) != run_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise BridgeError(400, "valid run id required", False) from None
        return self.bridge.cancel(run_id)

    def notifications(self):
        with self.bridge.tx() as db:
            self.expire_delivery_claims(db)
            rows = db.execute("""SELECT n.id AS draft_id,p.id AS run_id,p.state AS run_state,
                j.id AS job_id,j.state AS job_state,j.pr_url FROM native_drafts n
                JOIN operations p ON p.kind='paperclip' AND p.key='native-telegram-' || n.id
                LEFT JOIN operations h ON h.kind='hermes' AND h.key=p.external_id
                LEFT JOIN jobs j ON j.director_run=h.id
                ORDER BY n.created DESC LIMIT 30""").fetchall()
            for row in rows:
                state = row["job_state"] or row["run_state"]
                identity = json.dumps([row["draft_id"], row["job_id"], state, row["pr_url"]])
                notification_id = hashlib.sha256(identity.encode()).hexdigest()
                text = f"LOOP: {state}.\nЗапуск: {row['run_id']}"
                if row["job_id"]:
                    text += f"\nЗадача: {row['job_id']}"
                if row["pr_url"] and state == "ready_pr":
                    text += "\nГотов PR на ваше рассмотрение:\n" + row["pr_url"] + "\nMerge и production deploy не выполнялись."
                else:
                    text += "\nГотовность PR ещё не подтверждена. /loop_status"
                db.execute("INSERT OR IGNORE INTO native_notifications(id,text,created) VALUES(?,?,?)",
                           (notification_id, text, time.time()))
            return {"pending": [dict(r) for r in db.execute(
                "SELECT id FROM native_notifications WHERE state='pending' ORDER BY created LIMIT 10")],
                "delivery_unknown": db.execute("SELECT count(*) FROM native_notifications WHERE state='delivery_unknown'").fetchone()[0]}

    @staticmethod
    def expire_delivery_claims(db):
        # Hermes can restart independently of Bridge. Expiry never resends.
        db.execute("""UPDATE native_notifications SET state='delivery_unknown'
            WHERE state='sending' AND (claimed_at IS NULL OR claimed_at<?)""", (time.time() - 120,))

    def notification_action(self, notification_id, action, payload):
        with self.bridge.tx() as db:
            if action == "claim":
                changed = db.execute("UPDATE native_notifications SET state='sending',claimed_at=? WHERE id=? AND state='pending'",
                                     (time.time(), notification_id)).rowcount
                if not changed:
                    raise BridgeError(409, "notification already claimed; no automatic resend", False)
                return dict(db.execute("SELECT id,text FROM native_notifications WHERE id=?", (notification_id,)).fetchone())
            if action == "settle" and type(payload.get("delivered")) is bool:
                state = "delivered" if payload["delivered"] else "delivery_unknown"
                db.execute("UPDATE native_notifications SET state=? WHERE id=? AND state IN ('sending','delivery_unknown')", (state, notification_id))
                row = db.execute("SELECT state FROM native_notifications WHERE id=?", (notification_id,)).fetchone()
                if not row:
                    raise BridgeError(404, "notification unavailable", False)
                return {"state": row["state"]}
        raise BridgeError(400, "invalid notification settlement", False)

    def route(self, method, path, payload):
        if method == "GET" and path == "/v1/chat/status":
            return self.status()
        if method == "POST" and path == "/v1/chat/drafts":
            return self.draft(payload)
        if method == "POST" and path == "/v1/native/preview":
            return self.preview(payload)
        if method == "POST" and path == "/v1/native/preview-receipt":
            return self.preview_receipt(payload)
        if method == "POST" and path == "/v1/native/confirm":
            return self.confirm(payload)
        if method == "POST" and path == "/v1/native/stop":
            return self.stop(payload)
        if method == "GET" and path == "/v1/native/notifications":
            return self.notifications()
        match = re.fullmatch(r"/v1/native/notifications/([a-f0-9]{64})/(claim|settle)", path)
        if method == "POST" and match:
            return self.notification_action(match[1], match[2], payload)
        raise BridgeError(404, "native operation unavailable", False)
