"""Minimal stdio MCP tool for an isolated Hermes Director. No terminal or scheduler."""
import json
import os
import sys
try:
    from .bridge import JsonHTTP, secret
except ImportError:
    from bridge import JsonHTTP, secret

def serve(client):
    for line in sys.stdin:
        try:
            request=json.loads(line);method=request.get("method");params=request.get("params",{});request_id=request.get("id")
            if request_id is None:continue
            if method=="initialize":result={"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"loop-director","version":"1.0.0"}}
            elif method=="tools/list":result={"tools":[{"name":"loop_propose_job","description":"Propose a pre-approved job template under the current trusted Bridge run_id and generation. Never executes arbitrary commands.","inputSchema":{"type":"object","additionalProperties":False,"required":["job_id","run_id","generation","template"],"properties":{"job_id":{"type":"string","pattern":"^[a-z0-9][a-z0-9-]{2,40}$"},"run_id":{"type":"string"},"generation":{"type":"integer","minimum":1},"template":{"type":"string"}}}}]}
            elif method=="tools/call" and params.get("name")=="loop_propose_job":
                result={"content":[{"type":"text","text":json.dumps(client.call("POST","/v1/jobs",params.get("arguments",{})))}]}
            elif method=="ping":result={}
            else:raise ValueError("unsupported method")
            response={"jsonrpc":"2.0","id":request_id,"result":result}
        except Exception:response={"jsonrpc":"2.0","id":request.get("id") if isinstance(locals().get("request"),dict) else None,"error":{"code":-32602,"message":"Bridge rejected request; inspect current attempt and template"}}
        print(json.dumps(response),flush=True)
if __name__=="__main__":serve(JsonHTTP(os.environ["LOOP_BRIDGE_URL"],secret(os.environ["LOOP_DIRECTOR_TOKEN_FILE"])))
