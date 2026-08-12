from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "provenance" / "import-inventory.json"
IMPORTED_ROOT = ROOT / "services" / "collector" / "src" / "imported"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def status_digest(path: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-uall"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    return digest(result.stdout)


def verify() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    imports = inventory.get("imports", [])
    if not imports:
        raise ValueError("provenance inventory has no imports")

    destinations: set[str] = set()
    required = {
        "source_repository",
        "source_path",
        "source_commit",
        "source_sha256",
        "destination",
        "import_mode",
        "review_status",
    }
    for item in imports:
        if set(item) != required:
            raise ValueError(f"invalid inventory fields for {item.get('destination', '<unknown>')}")
        if item["destination"] in destinations:
            raise ValueError(f"duplicate destination: {item['destination']}")
        destinations.add(item["destination"])
        if item["import_mode"] != "tracked_commit_exact_bytes":
            raise ValueError(f"mutable import mode: {item['destination']}")
        if not COMMIT.fullmatch(item["source_commit"]):
            raise ValueError(f"invalid source commit: {item['destination']}")
        if not SHA256.fullmatch(item["source_sha256"]):
            raise ValueError(f"invalid source hash: {item['destination']}")
        destination = (ROOT / item["destination"]).resolve()
        if ROOT not in destination.parents or not destination.is_file():
            raise ValueError(f"missing or unsafe destination: {item['destination']}")
        if digest(destination.read_bytes()) != item["source_sha256"]:
            raise ValueError(f"destination bytes differ from source: {item['destination']}")

    actual = {
        path.relative_to(ROOT).as_posix()
        for path in IMPORTED_ROOT.glob("*.ts")
        if path.is_file()
    }
    if actual != destinations:
        raise ValueError(f"undeclared or missing imports: {sorted(actual ^ destinations)}")

    for worktree in inventory.get("source_worktrees", []):
        before = worktree["status_sha256_before"]
        after = worktree["status_sha256_after"]
        if before != after or not SHA256.fullmatch(before):
            raise ValueError(f"source worktree fingerprint mismatch: {worktree['name']}")
        current = status_digest(Path(worktree["path"]))
        if current != after:
            raise ValueError(f"source worktree changed after import: {worktree['name']}")


if __name__ == "__main__":
    verify()
    print("provenance verification passed")
