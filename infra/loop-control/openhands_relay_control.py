#!/usr/bin/python3
"""Stop only the LOOP relay process inside the Bridge container."""
import json
import subprocess
import sys

if sys.argv[1:] != ["stop"]:
    raise SystemExit("usage: openhands-relay-control stop")

code = r'''import os, signal
found = []
for name in os.listdir("/proc"):
    if not name.isdigit() or name == "1":
        continue
    try:
        command = open("/proc/" + name + "/cmdline", "rb").read().replace(b"\0", b" ").decode()
    except (OSError, UnicodeError):
        continue
    if command.strip() == "python3 /opt/loop/openhands_relay.py":
        found.append(int(name))
for pid in found:
    os.kill(pid, signal.SIGTERM)
print(len(found))
'''
result = subprocess.run(
    ["/usr/bin/docker", "exec", "loop-control-bridge-1", "python3", "-c", code],
    capture_output=True, text=True,
)
if result.returncode not in {0, 1}:
    raise SystemExit("relay cleanup failed")
