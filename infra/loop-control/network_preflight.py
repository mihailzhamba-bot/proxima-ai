#!/usr/bin/python3
"""Create missing LOOP private networks and reject any configuration drift."""

from __future__ import annotations

import argparse
import json
import subprocess


NETWORKS = {
    "loop-hermes-private": {"subnet": "172.30.240.0/24", "gateway": "172.30.240.1"},
    "loop-openhands-private": {"subnet": "172.30.241.0/24", "gateway": "172.30.241.1"},
}


def inspect(name: str) -> dict | None:
    result = subprocess.run(
        ["/usr/bin/docker", "network", "inspect", name],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return None
    payload = json.loads(result.stdout)
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise RuntimeError("invalid Docker network inspection")
    return payload[0]


def valid(observed: dict, expected: dict) -> bool:
    configs = observed.get("IPAM", {}).get("Config", [])
    return (
        observed.get("Driver") == "bridge"
        and observed.get("Internal") is True
        and isinstance(configs, list)
        and len(configs) == 1
        and configs[0].get("Subnet") == expected["subnet"]
        and configs[0].get("Gateway") == expected["gateway"]
    )


def create(name: str, expected: dict) -> None:
    subprocess.run(
        [
            "/usr/bin/docker",
            "network",
            "create",
            "--driver",
            "bridge",
            "--internal",
            "--subnet",
            expected["subnet"],
            "--gateway",
            expected["gateway"],
            name,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.ensure == args.check:
        raise SystemExit("choose exactly one of --ensure or --check")
    result = {}
    for name, expected in NETWORKS.items():
        observed = inspect(name)
        if observed is None and args.ensure:
            create(name, expected)
            observed = inspect(name)
        result[name] = "ok" if observed is not None and valid(observed, expected) else "error"
    print(json.dumps(result, sort_keys=True))
    if any(value != "ok" for value in result.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
