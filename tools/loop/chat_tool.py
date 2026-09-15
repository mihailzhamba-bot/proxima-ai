"""Read/draft-only MCP for native Telegram; no execution/ingress credential."""
import json
import os
import sys
try:
    from .bridge import JsonHTTP, secret
except ImportError:
    from bridge import JsonHTTP, secret

TOOLS = [
    {"name": "loop_get_status", "description": "Read actual LOOP queue, recent runs/jobs and PR links. Preserve timestamps and distinguish stored job state from fresh observations. Never call a task complete without its receipt.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "loop_prepare_action", "description": "Prepare an admitted fixed job template for Mike to review. Does not launch anything. Return the exact /loop_review command to Mike. Arbitrary development is not yet admitted.",
     "inputSchema": {"type": "object", "properties": {"template": {"type": "string"}}, "required": ["template"], "additionalProperties": False}},
]


def serve(client):
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or request.get("id") is None:
                continue
            method, params = request.get("method"), request.get("params", {})
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "loop-chat", "version": "1.0.0"}}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "ping":
                result = {}
            elif method == "tools/call":
                name, args = params.get("name"), params.get("arguments", {})
                if name == "loop_get_status" and args == {}:
                    value = client.call("GET", "/v1/chat/status")
                elif name == "loop_prepare_action" and isinstance(args, dict) and set(args) == {"template"}:
                    value = client.call("POST", "/v1/chat/drafts", args)
                else:
                    raise ValueError()
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
            else:
                raise ValueError()
            response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except Exception:
            response = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                        "error": {"code": -32602, "message": "LOOP read/draft request unavailable; no execution confirmed"}}
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    serve(JsonHTTP(os.environ["LOOP_BRIDGE_URL"], secret(os.environ["LOOP_CHAT_TOKEN_FILE"]), trusted_bridge=True))
