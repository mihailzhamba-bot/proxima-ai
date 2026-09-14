#!/usr/bin/python3 -I
"""Native Claudette acceptance for the dedicated LOOP worker boundary."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import os
from pathlib import Path
import pwd
import stat
import subprocess
import threading
import urllib.request


CODEX="/opt/loop-openhands-agent/node_modules/.bin/codex"
ACP="/opt/loop-openhands-agent/node_modules/.bin/codex-acp"
HOME="/srv/loop-worker/agent-home"
CODEX_HOME="/srv/loop-worker/codex-home"
WORKSPACE="/srv/loop-worker/workspaces"
KEY=Path("/etc/loop-worker/secrets/openhands.env")


def session_key() -> str:
    values=dict(line.split("=",1) for line in KEY.read_text().splitlines() if "=" in line)
    value=values.get("LOCAL_BACKEND_API_KEY","")
    if len(value)<32:raise RuntimeError("dedicated client key missing")
    return value


def local_network_probe() -> tuple[ThreadingHTTPServer,threading.Thread,str,bool]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            raw=b"loop-network-control\n";self.send_response(200);self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
        def log_message(self,*_args):pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f"http://127.0.0.1:{server.server_port}/"
    control=Path("/usr/bin/curl").is_file() and subprocess.run(["/usr/sbin/runuser","-u","loop-oh-agent","--","/usr/bin/curl","-fsS","--max-time","2",url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    return server,thread,url,control


def main() -> None:
    checks={}
    checks["agent_server"]=subprocess.run(["/usr/bin/systemctl","is-active","--quiet","loop-openhands-agent-server.service"]).returncode==0
    checks["volume"]=subprocess.run(["/usr/local/sbin/loop-worker-volume","--check"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    version_env={"PATH":"/opt/loop-openhands-agent/node_modules/.bin:/usr/local/bin:/usr/bin:/bin","HOME":HOME,"CODEX_HOME":CODEX_HOME,"LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
    versions=[(ACP,"@agentclientprotocol/codex-acp 1.1.7"),(CODEX,"codex-cli 0.151.0")];observed=[subprocess.run([binary,"--version"],capture_output=True,text=True,timeout=10,env=version_env) for binary,_expected in versions]
    checks["tool_versions"]=all(result.returncode==0 and result.stdout.strip()==expected and not result.stderr.strip() for result,(_binary,expected) in zip(observed,versions,strict=True))
    distributions={"openhands-agent-server":"1.44.0","openhands-sdk":"1.44.0","openhands-tools":"1.44.0","openhands-workspace":"1.44.0"};code="import importlib.metadata as m,json; names="+repr(sorted(distributions))+"; print(json.dumps({name:m.version(name) for name in names},sort_keys=True))"
    package_result=subprocess.run(["/opt/loop-openhands-agent/venv/bin/python","-I","-c",code],capture_output=True,text=True,timeout=10,env=version_env)
    try:package_versions=json.loads(package_result.stdout) if package_result.returncode==0 and not package_result.stderr.strip() else None
    except json.JSONDecodeError:package_versions=None
    checks["openhands_versions"]=package_versions==distributions
    account=pwd.getpwnam("loop-oh-agent");auth=Path(CODEX_HOME)/"auth.json";info=auth.lstat()
    try:auth_payload=json.loads(auth.read_text());tokens=auth_payload.get("tokens",{});auth_shape=auth_payload.get("auth_mode")=="chatgpt" and auth_payload.get("OPENAI_API_KEY") is None and all(isinstance(tokens.get(name),str) and len(tokens[name])>=16 for name in ["access_token","account_id","id_token","refresh_token"])
    except Exception:auth_shape=False
    checks["auth_mode"]=stat.S_ISREG(info.st_mode) and not auth.is_symlink() and info.st_uid==account.pw_uid and stat.S_IMODE(info.st_mode)==0o600 and auth_shape
    login=subprocess.run(["/usr/sbin/runuser","-u","loop-oh-agent","--","/usr/bin/env",*[f"{key}={value}" for key,value in version_env.items()],CODEX,"login","status"],capture_output=True,text=True,timeout=15)
    login_lines=[line for line in (login.stdout+"\n"+login.stderr).splitlines() if line];allowed_login=lambda line:line=="Logged in using ChatGPT" or line.startswith("WARNING: proceeding, even though we could not create PATH aliases:")
    checks["chatgpt_login"]=login.returncode==0 and "Logged in using ChatGPT" in login_lines and all(allowed_login(line) for line in login_lines)
    server,thread,url,control=local_network_probe();checks["network_control"]=control
    try:
        command=[
            "/usr/sbin/runuser","-u","loop-oh-agent","--","env",f"HOME={HOME}","CODEX_HOME=/etc/loop-openhands-agent",CODEX,
            "sandbox","-P","loop-worker","-C",WORKSPACE,"/bin/sh","-c",
            "test ! -r /srv/loop-worker/codex-home/auth.json && "
            "touch /srv/loop-worker/workspaces/.loop-permission-probe && "
            "test -f /srv/loop-worker/workspaces/.loop-permission-probe && "
            "rm /srv/loop-worker/workspaces/.loop-permission-probe && "
            "test ! -r /srv/proxima-ai && "
            f"! /usr/bin/curl -fsS --max-time 2 {url} >/dev/null 2>&1",
        ]
        checks["codex_sandbox"]=control and subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20).returncode==0
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
    key=session_key()
    def api(path: str) -> dict:
        request=urllib.request.Request("http://127.0.0.1:18002"+path,headers={"X-Session-API-Key":key})
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    profile=api("/api/agent-profiles/loop-codex")["profile"];profile_id=profile.get("id");revision=profile.get("revision")
    checks["profile"]=profile.get("acp_model")=="gpt-5.6-sol" and profile.get("acp_command")=="/opt/loop-openhands-agent/bin/codex-acp" and profile.get("acp_args")==[] and profile.get("acp_session_mode")=="agent" and profile.get("acp_startup_timeout")==90.0 and profile.get("acp_prompt_timeout")==1800.0 and profile.get("mcp_server_refs")==[] and isinstance(profile_id,str) and isinstance(revision,int)
    checks["profile_active"]=api("/api/agent-profiles").get("active_agent_profile_id")==profile_id
    binding_path=Path("/etc/loop-worker/templates.json");binding_info=binding_path.lstat();binding=json.loads(binding_path.read_text())
    checks["profile_binding"]=stat.S_ISREG(binding_info.st_mode) and not binding_path.is_symlink() and binding_info.st_uid==0 and not binding_info.st_mode&0o022 and binding.get("profile_fedor")==profile_id and binding.get("profile_fedor_revision")==revision
    print(json.dumps(checks,sort_keys=True))
    if not all(checks.values()):raise SystemExit(1)


if __name__=="__main__":main()
