from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
from pathlib import Path
from pathlib import PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "provenance" / "import-inventory.json"
IMPORTED_ROOT = ROOT / "services" / "collector" / "src" / "imported"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")


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


def git_bytes(path: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=path,
        check=True,
        capture_output=True,
    )
    return result.stdout


def safe_source_path(value: str) -> str:
    source = PurePosixPath(value)
    if source.is_absolute() or not source.parts or ".." in source.parts or "\n" in value or "\r" in value:
        raise ValueError(f"unsafe source path: {value!r}")
    return value


def git_object_sha1(object_type: str, content: bytes) -> str:
    header = f"{object_type} {len(content)}\0".encode()
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def tree_entries(content: bytes) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    offset = 0
    while offset < len(content):
        space = content.find(b" ", offset)
        separator = content.find(b"\0", space + 1)
        if space < 0 or separator < 0 or separator + 21 > len(content):
            raise ValueError("malformed Git tree object")
        mode = content[offset:space].decode("ascii")
        name = content[space + 1 : separator].decode("utf-8")
        if not name or "/" in name or name in entries:
            raise ValueError("unsafe or duplicate Git tree entry")
        entries[name] = (mode, content[separator + 1 : separator + 21].hex())
        offset = separator + 21
    return entries


def attested_paths(attestation: dict) -> dict[str, str]:
    if set(attestation) != {
        "schema_version",
        "source_repository",
        "source_commit",
        "root_tree",
        "objects",
        "paths",
    } or attestation["schema_version"] != 1:
        raise ValueError("invalid source attestation fields")
    commit = attestation["source_commit"]
    root_tree = attestation["root_tree"]
    if not SHA1.fullmatch(commit) or not SHA1.fullmatch(root_tree):
        raise ValueError("invalid attestation commit or root tree")

    objects: dict[str, tuple[str, bytes]] = {}
    for object_id, record in attestation["objects"].items():
        if not SHA1.fullmatch(object_id) or set(record) != {"type", "content_base64"}:
            raise ValueError("invalid attested Git object record")
        object_type = record["type"]
        if object_type not in {"commit", "tree"}:
            raise ValueError(f"unsupported attested Git object type: {object_type}")
        try:
            content = base64.b64decode(record["content_base64"], validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError(f"invalid base64 for attested object: {object_id}") from error
        if git_object_sha1(object_type, content) != object_id:
            raise ValueError(f"attested Git object hash mismatch: {object_id}")
        objects[object_id] = (object_type, content)

    commit_record = objects.get(commit)
    if commit_record is None or commit_record[0] != "commit":
        raise ValueError("attested commit object missing")
    declared_tree = commit_record[1].splitlines()[0]
    if declared_tree != f"tree {root_tree}".encode():
        raise ValueError("attested commit does not reference root tree")

    resolved: dict[str, str] = {}
    for source_path, declared_blob in attestation["paths"].items():
        safe_source_path(source_path)
        if not SHA1.fullmatch(declared_blob):
            raise ValueError(f"invalid attested blob id: {source_path}")
        current_tree = root_tree
        parts = PurePosixPath(source_path).parts
        for index, component in enumerate(parts):
            record = objects.get(current_tree)
            if record is None or record[0] != "tree":
                raise ValueError(f"attested tree missing for path: {source_path}")
            entry = tree_entries(record[1]).get(component)
            if entry is None:
                raise ValueError(f"attested path missing from tree: {source_path}")
            mode, object_id = entry
            if index < len(parts) - 1:
                if mode not in {"40000", "040000"}:
                    raise ValueError(f"non-tree component in attested path: {source_path}")
                current_tree = object_id
            elif mode not in {"100644", "100755"} or object_id != declared_blob:
                raise ValueError(f"attested blob differs from tree entry: {source_path}")
        resolved[source_path] = declared_blob
    return resolved


def verify() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    imports = inventory.get("imports", [])
    if not imports:
        raise ValueError("provenance inventory has no imports")

    worktrees = inventory.get("source_worktrees", [])
    attestations: dict[tuple[str, str], dict[str, str]] = {}
    for reference in inventory.get("source_attestations", []):
        if set(reference) != {"source_repository", "source_commit", "path"}:
            raise ValueError("invalid source attestation reference")
        path = (ROOT / reference["path"]).resolve()
        if ROOT not in path.parents or not path.is_file():
            raise ValueError(f"missing or unsafe source attestation: {reference['path']}")
        attestation = json.loads(path.read_text(encoding="utf-8"))
        if attestation["source_repository"] != reference["source_repository"]:
            raise ValueError("attestation source repository mismatch")
        if attestation["source_commit"] != reference["source_commit"]:
            raise ValueError("attestation source commit mismatch")
        key = (reference["source_repository"], reference["source_commit"])
        if key in attestations:
            raise ValueError("duplicate source attestation")
        attestations[key] = attested_paths(attestation)

    destinations: set[str] = set()
    repositories: dict[str, tuple[Path, str]] = {}
    for worktree in worktrees:
        path = Path(worktree["path"])
        before = worktree["status_sha256_before"]
        after = worktree["status_sha256_after"]
        if before != after or not SHA256.fullmatch(before):
            raise ValueError(f"source worktree fingerprint mismatch: {worktree['name']}")
        if not path.exists():
            continue
        remote = git_bytes(path, "remote", "get-url", "origin").decode().strip()
        if remote in repositories:
            raise ValueError(f"duplicate source repository worktree: {remote}")
        repositories[remote] = (path, worktree["tracked_commit"])
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
        if not SHA1.fullmatch(item["source_commit"]):
            raise ValueError(f"invalid source commit: {item['destination']}")
        if not SHA256.fullmatch(item["source_sha256"]):
            raise ValueError(f"invalid source hash: {item['destination']}")
        source_path = safe_source_path(item["source_path"])
        paths = attestations.get((item["source_repository"], item["source_commit"]))
        if paths is None or source_path not in paths:
            raise ValueError(f"source path has no commit-tree attestation: {item['destination']}")
        destination = (ROOT / item["destination"]).resolve()
        if ROOT not in destination.parents or not destination.is_file():
            raise ValueError(f"missing or unsafe destination: {item['destination']}")
        destination_bytes = destination.read_bytes()
        if git_object_sha1("blob", destination_bytes) != paths[source_path]:
            raise ValueError(f"destination bytes differ from attested Git blob: {item['destination']}")
        if digest(destination_bytes) != item["source_sha256"]:
            raise ValueError(f"destination bytes differ from source: {item['destination']}")

        repository = repositories.get(item["source_repository"])
        if repository is not None:
            source_worktree, tracked_commit = repository
            if item["source_commit"] != tracked_commit:
                raise ValueError(f"source commit differs from locked worktree commit: {item['destination']}")
            source_bytes = git_bytes(source_worktree, "show", f"{item['source_commit']}:{source_path}")
            if source_bytes != destination_bytes:
                raise ValueError(f"local source blob differs from destination: {item['destination']}")

    actual = {
        path.relative_to(ROOT).as_posix()
        for path in IMPORTED_ROOT.glob("*.ts")
        if path.is_file()
    }
    if actual != destinations:
        raise ValueError(f"undeclared or missing imports: {sorted(actual ^ destinations)}")

    for worktree in worktrees:
        path = Path(worktree["path"])
        if not path.exists():
            continue
        current = status_digest(path)
        if current != worktree["status_sha256_after"]:
            raise ValueError(f"source worktree changed after import: {worktree['name']}")


if __name__ == "__main__":
    verify()
    print("provenance verification passed")
