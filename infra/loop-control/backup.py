#!/usr/bin/python3
"""Encrypted, component-aware LOOP backup. Receipts never contain secrets."""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
import time

os.umask(0o077)
BACKUP_ROOT = Path("/var/backups/loop/daily")
STATUS_PATH = Path("/var/lib/loop/backups/status.json")
LAST_SUCCESS_PATH = Path("/var/lib/loop/backups/last-success.json")
LOCK_PATH = Path("/run/loop-backup/lock")
RUNTIME_ROOT = Path("/run/loop-backup")
KEY_PATH = Path("/etc/loop/secrets/backup_encryption")
POSTGRES_CONTAINER = "loop-control-postgres-1"
PAPERCLIP_DB = "paperclip"
STATE_ROOTS = {
    "paperclip": Path("/var/lib/docker/volumes/loop-control_paperclip/_data"),
    "bridge": Path("/var/lib/docker/volumes/loop-control_bridge/_data"),
    "hermes": Path("/var/lib/docker/volumes/loop-control_hermes/_data"),
    "telegram": Path("/var/lib/docker/volumes/loop-control_telegram/_data"),
}
STATE_EXCLUDES = {
    "paperclip": (Path("instances/default/data/backups"),),
}
MANDATORY_STATE = {"paperclip", "bridge", "hermes"}
MANDATORY_FILES = {
    "paperclip": {"instances/default/secrets/master.key", "instances/default/secrets/decision-signing.key"},
    "bridge": {"bridge.sqlite"},
    "hermes": {"auth.json", "state.db", "runs_idempotency.db", "response_store.db"},
}
RECOVERY_TREES = [
    Path("/etc/loop"), Path("/etc/loop-tunnel"), Path("/etc/loop-proxy"),
    Path("/etc/loop-openhands-tunnel"), Path("/opt/loop-control"),
]
RECOVERY_KEYS = [
    Path("/var/lib/loop-tunnel/id_ed25519"),
    Path("/var/lib/loop-openhands-tunnel/id_ed25519"),
]
RECOVERY_UNITS = [
    "loop-egress-tunnel.service", "loop-egress-proxy.service",
    "loop-openhands-tunnel.service", "loop-openhands-relay.service",
    "loop-network-preflight.service", "loop-control.service",
    "loop-backup.service", "loop-backup.timer", "loop-health.service", "loop-health.timer",
]
RECOVERY_PROGRAMS = ["loop-backup", "loop-health", "loop-openhands-relay-control", "loop-network-preflight"]


def run(args: list[str], *, stdin=None, stdout=None) -> subprocess.CompletedProcess:
    return subprocess.run(args, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE, check=True)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def keyed_digest(path: Path, key_path: Path) -> str:
    value = hmac.new(key_path.read_bytes(), digestmod=hashlib.sha256)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def tree_size(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def sqlite_backup(source: Path, destination: Path) -> None:
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            check = dst.execute("PRAGMA quick_check").fetchone()
            if not check or check[0] != "ok":
                raise RuntimeError("SQLite quick_check failed")
    destination.chmod(0o600)


def copy_component_state(name: str, source: Path, destination: Path, inventory: dict) -> None:
    if not source.is_dir():
        if name in MANDATORY_STATE:
            raise RuntimeError(f"Mandatory component state is missing: {name}")
        inventory[name] = {"present": False}
        return
    destination.mkdir(mode=0o700)
    databases = []
    files = []
    for item in sorted(source.rglob("*")):
        if item.is_symlink():
            raise RuntimeError(f"Symlink in component state is forbidden: {name}")
        if not item.is_file():
            continue
        relative = item.relative_to(source)
        if any(relative == prefix or prefix in relative.parents for prefix in STATE_EXCLUDES.get(name, ())):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lowered = item.name.lower()
        database_suffixes = (".db", ".sqlite", ".sqlite3")
        if lowered.endswith(database_suffixes):
            sqlite_backup(item, target)
            databases.append(str(relative))
        elif lowered.endswith(tuple(
            suffix + sidecar for suffix in database_suffixes for sidecar in ("-wal", "-shm")
        )):
            continue
        else:
            shutil.copy2(item, target)
            target.chmod(0o600)
            files.append(str(relative))
    inventory[name] = {
        "present": True, "sqlite_backups": databases, "copied_file_count": len(files),
    }
    copied = {str(item.relative_to(destination)) for item in destination.rglob("*") if item.is_file()}
    missing = MANDATORY_FILES.get(name, set()) - copied
    if missing:
        raise RuntimeError(f"Mandatory component files are missing: {name}")


def add_tree(archive: tarfile.TarFile, source: Path, arc_root: str, *, excluded: set[Path] | None = None) -> None:
    excluded = excluded or set()
    for item in sorted(source.rglob("*")):
        if item.is_symlink():
            raise RuntimeError(f"Symlink in recovery tree is forbidden: {source}")
        if item in excluded or not item.is_file():
            continue
        archive.add(item, arcname=str(Path(arc_root) / item.relative_to(source)), recursive=False)


def validate_recovery_sources() -> dict:
    paths = [*RECOVERY_TREES, *RECOVERY_KEYS]
    paths += [Path("/etc/systemd/system") / name for name in RECOVERY_UNITS]
    paths += [Path("/usr/local/sbin") / name for name in RECOVERY_PROGRAMS]
    for path in paths:
        info = path.lstat()
        if path.is_symlink() or (not path.is_dir() and not stat.S_ISREG(info.st_mode)):
            raise RuntimeError(f"Required recovery artifact is invalid: {path}")
    return {
        "trees": [str(path) for path in RECOVERY_TREES],
        "keys": [str(path) for path in RECOVERY_KEYS],
        "units": list(RECOVERY_UNITS),
        "programs": list(RECOVERY_PROGRAMS),
    }


def postgres_inventory(container: str, database: str) -> dict:
    sql = """
CREATE OR REPLACE FUNCTION pg_temp.loop_counts()
RETURNS TABLE(name text, rows bigint) LANGUAGE plpgsql AS $$
DECLARE item record; amount bigint;
BEGIN
  FOR item IN SELECT table_schema,table_name FROM information_schema.tables
    WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2
  LOOP
    EXECUTE format('SELECT count(*) FROM %I.%I',item.table_schema,item.table_name) INTO amount;
    name:=item.table_schema||'.'||item.table_name; rows:=amount; RETURN NEXT;
  END LOOP;
END $$;
SELECT json_build_object(
  'schemas',(SELECT count(DISTINCT split_part(name,'.',1)) FROM pg_temp.loop_counts()),
  'tables',(SELECT count(*) FROM pg_temp.loop_counts()),
  'rows',(SELECT coalesce(sum(rows),0) FROM pg_temp.loop_counts()),
  'nonempty',(SELECT coalesce(json_agg(name ORDER BY rows DESC,name) FILTER (WHERE rows>0),'[]'::json) FROM (SELECT * FROM pg_temp.loop_counts() ORDER BY rows DESC,name LIMIT 10) q)
)::text;
"""
    raw = subprocess.check_output(["docker","exec",container,"psql","-U","postgres","-d",database,"-Atq","-c",sql],text=True).strip().splitlines()[-1]
    result = json.loads(raw)
    if result.get("schemas",0)<1 or result.get("tables",0)<1 or result.get("rows",0)<1 or not result.get("nonempty"):
        raise RuntimeError("Restored PostgreSQL inventory is empty")
    return result


def postgres_restore_test(database_dump: Path, scratch: Path, image: str, stamp: str) -> dict:
    container="loop-backup-restore-"+stamp.lower();volume=container
    password=scratch/"restore-password";password.write_text(os.urandom(32).hex());password.chmod(0o600)
    run(["docker","volume","create",volume],stdout=subprocess.DEVNULL)
    try:
        run(["docker","run","-d","--name",container,"--network","none","--memory","1g","--cpus","1","--pids-limit","128","-v",volume+":/var/lib/postgresql/data","-v",str(password)+":/run/secrets/postgres:ro","-e","POSTGRES_PASSWORD_FILE=/run/secrets/postgres",image],stdout=subprocess.DEVNULL)
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            if subprocess.run(["docker","exec",container,"pg_isready","-U","postgres","-d","postgres"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:break
            time.sleep(2)
        else:raise RuntimeError("Temporary PostgreSQL restore did not become ready")
        with database_dump.open("rb") as source:
            run(["docker","exec","-i",container,"pg_restore","-U","postgres","-d","postgres","--exit-on-error","--no-owner","--no-acl"],stdin=source,stdout=subprocess.DEVNULL)
        inventory=postgres_inventory(container,"postgres")
        return {"engine":"native pg_restore into isolated PostgreSQL","restore_verified":True,**inventory}
    finally:
        subprocess.run(["docker","rm","-f",container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(["docker","volume","rm",volume],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def main() -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    with LOCK_PATH.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("LOOP backup already running")

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = BACKUP_ROOT / stamp
        receipt = {
            "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "status": "running",
            "target": str(target),
            "retention": "no automatic deletion; disk monitor guards free space",
        }
        write_json(STATUS_PATH, receipt)
        try:
            target.mkdir(mode=0o700)
            disk_free = shutil.disk_usage(BACKUP_ROOT).free
            runtime_free = shutil.disk_usage(RUNTIME_ROOT).free
            postgres_bytes = int(subprocess.check_output([
                "docker", "exec", POSTGRES_CONTAINER, "psql", "-U", "postgres", "-d", PAPERCLIP_DB,
                "-Atqc", "SELECT pg_database_size(current_database())",
            ], text=True).strip())
            source_bytes = postgres_bytes + sum(tree_size(path) for path in STATE_ROOTS.values())
            source_bytes += tree_size(Path("/etc/loop")) + tree_size(Path("/etc/loop-tunnel"))
            source_bytes += tree_size(Path("/etc/loop-proxy"))
            runtime_required = max(256 * 1024**2, 3 * source_bytes)
            if disk_free < 5 * 1024**3 + source_bytes:
                raise RuntimeError("Backup disk floor reached")
            if runtime_free < runtime_required:
                raise RuntimeError("Backup runtime scratch floor reached")
            if KEY_PATH.stat().st_mode & 0o077:
                raise RuntimeError("Backup encryption key permissions are too broad")
            recovery_manifest = validate_recovery_sources()
            postgres_image = subprocess.check_output(
                ["docker", "inspect", "--format", "{{.Image}}", POSTGRES_CONTAINER], text=True,
            ).strip()
            if not re.fullmatch(r"sha256:[a-f0-9]{64}", postgres_image):
                raise RuntimeError("Running PostgreSQL image is not content-addressed")
            with tempfile.TemporaryDirectory(prefix="attempt-", dir=RUNTIME_ROOT) as scratch_name:
                scratch = Path(scratch_name)
                plaintext_archive = scratch / "loop-backup.tar.gz"
                decrypted_check = scratch / "loop-backup.check.tar.gz"
                database_dump = scratch / "paperclip.dump"
                with database_dump.open("wb") as output:
                    run(["docker", "exec", POSTGRES_CONTAINER, "pg_dump", "-U", "postgres", "-d",
                         PAPERCLIP_DB, "--format=custom", "--no-owner", "--no-acl"], stdout=output)
                with database_dump.open("rb") as input_handle:
                    run(["docker", "exec", "-i", POSTGRES_CONTAINER, "pg_restore", "--list"],
                        stdin=input_handle, stdout=subprocess.DEVNULL)
                restore_evidence = postgres_restore_test(database_dump, scratch, postgres_image, stamp)

                component_inventory: dict[str, dict] = {}
                state = scratch / "state"
                state.mkdir(mode=0o700)
                for name, source in STATE_ROOTS.items():
                    copy_component_state(name, source, state / name, component_inventory)

                paperclip_key = Path(
                    "/var/lib/docker/volumes/loop-control_paperclip/_data/instances/default/secrets/master.key"
                )
                if not paperclip_key.is_file():
                    raise RuntimeError("Paperclip secret-store master key is missing")
                secret_store = scratch / "paperclip-master.key"
                shutil.copy2(paperclip_key, secret_store)
                secret_store.chmod(0o600)

                with tarfile.open(plaintext_archive, "w:gz") as archive:
                    archive.add(database_dump, arcname="paperclip.dump", recursive=False)
                    archive.add(secret_store, arcname="paperclip-master.key", recursive=False)
                    add_tree(archive, state, "state")
                    for path in RECOVERY_TREES:
                        add_tree(archive, path, path.name, excluded={KEY_PATH})
                    for path in RECOVERY_KEYS:
                        archive.add(path, arcname="keys/" + path.parent.name + "/" + path.name, recursive=False)
                    for unit in RECOVERY_UNITS:
                        archive.add(Path("/etc/systemd/system") / unit, arcname="systemd/" + unit, recursive=False)
                    for program in RECOVERY_PROGRAMS:
                        archive.add(Path("/usr/local/sbin") / program, arcname="sbin/" + program, recursive=False)
                    logrotate = Path("/etc/logrotate.d/loop-bootstrap")
                    if logrotate.is_file():
                        archive.add(logrotate, arcname="logrotate/loop-bootstrap", recursive=False)

                plaintext_digest = digest(plaintext_archive)
                encrypted = target / "loop-backup.tar.gz.enc"
                run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-salt",
                     "-in", str(plaintext_archive), "-out", str(encrypted), "-pass", "file:" + str(KEY_PATH)])
                encrypted.chmod(0o600)
                plaintext_archive.unlink()
                for child in list(scratch.iterdir()):
                    if child == decrypted_check:
                        continue
                    if child.is_dir():
                        shutil.rmtree(child)
                    elif child.exists():
                        child.unlink()
                run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
                     "-in", str(encrypted), "-out", str(decrypted_check), "-pass", "file:" + str(KEY_PATH)])
                if plaintext_digest != digest(decrypted_check):
                    raise RuntimeError("Encrypted backup roundtrip mismatch")
                with tarfile.open(decrypted_check, "r:gz") as archive:
                    members = archive.getnames()
            required = {"paperclip.dump", "paperclip-master.key"}
            if not required.issubset(members):
                raise RuntimeError("Required backup members are missing")
            receipt.update({
                "finished_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "status": "ok",
                "encrypted_file": str(encrypted),
                "encrypted_bytes": encrypted.stat().st_size,
                "sha256": digest(encrypted),
                "hmac_sha256": keyed_digest(encrypted, KEY_PATH),
                "database": {"dump_engine": "native pg_dump custom", "catalog_valid": True, **restore_evidence},
                "components": component_inventory,
                "paperclip_master_key_included": True,
                "config_included": True,
                "recovery_manifest": recovery_manifest,
                "encryption_roundtrip_verified": True,
                "archive_members": len(members),
                "preflight": {
                    "source_bytes_estimate": source_bytes,
                    "runtime_required_bytes": runtime_required,
                    "disk_floor_bytes": 5 * 1024**3,
                },
            })
            write_json(target / "receipt.json", receipt)
            write_json(STATUS_PATH, receipt)
            write_json(LAST_SUCCESS_PATH, receipt)
        except Exception as error:
            receipt.update({
                "finished_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "status": "error",
                "error_type": type(error).__name__,
            })
            write_json(STATUS_PATH, receipt)
            raise
        finally:
            # RuntimeDirectory is removed by systemd even after SIGKILL/OOM.
            # TemporaryDirectory handles normal completion and exceptions.
            pass


if __name__ == "__main__":
    main()
