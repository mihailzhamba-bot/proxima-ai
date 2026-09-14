#!/usr/bin/python3 -I
"""Harper gate for every commit, path and blob in an untrusted candidate range."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


SCANNER = Path("/opt/loop/secret_scan.py")
SHA = re.compile(r"[a-f0-9]{40}")
PROTECTED = re.compile(r"(^Makefile$|^tools/|^\.github/|(^|/)(package(-lock)?\.json|pyproject\.toml|uv\.lock)$|(^|/)[^/]*config[^/]*$|/tests/|^db/)")
MAX_COMMITS = 100
MAX_OBJECTS = 50_000
MAX_BLOB_BYTES = 5_000_000


def git(root: Path, *args: str, binary: bool = False):
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/var/empty",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    result = subprocess.run(
        ["/usr/bin/git", "--no-pager", "-c", "core.hooksPath=/dev/null", "-c", "safe.directory=*", "-C", str(root), *args],
        env=env,
        capture_output=True,
        text=not binary,
        timeout=120,
    )
    if result.returncode:
        raise ValueError("candidate history is invalid")
    return result.stdout


def load_scanner(path: Path = SCANNER):
    info = path.lstat()
    if not path.is_file() or path.is_symlink() or info.st_uid not in {0, os.getuid()} or info.st_mode & 0o022:
        raise ValueError("trusted secret scanner unavailable")
    spec = importlib.util.spec_from_file_location("loop_secret_scan", path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.self_test()
    return module


def valid_path(value: str) -> bool:
    path=PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and path.parts[0]!=".git"


def verify(root: Path, base: str, head: str, allowed: list[str], scanner_path: Path = SCANNER) -> dict:
    if not SHA.fullmatch(base) or not SHA.fullmatch(head) or not allowed or any(not valid_path(value) for value in allowed):
        raise ValueError("invalid history gate contract")
    git(root,"merge-base","--is-ancestor",base,head)
    commits=git(root,"rev-list","--reverse",base+".."+head).splitlines()
    if not commits or len(commits)>MAX_COMMITS or any(not SHA.fullmatch(value) for value in commits):
        raise ValueError("candidate commit count is outside policy")
    scanner=load_scanner(scanner_path)
    findings=[];changed=set()
    for commit in commits:
        raw=git(root,"cat-file","commit",commit,binary=True)
        findings.extend(scanner.inspect("history",f"commit/{commit}",raw))
        names=git(root,"diff-tree","--no-commit-id","--name-only","-r","-z",commit+"^!",binary=True)
        for encoded in names.split(b"\0"):
            if not encoded:continue
            name=encoded.decode("utf-8","strict")
            if not valid_path(name):raise ValueError("candidate path is invalid")
            if scanner.FORBIDDEN_NAMES.search(name):raise ValueError("candidate history used a forbidden secret filename")
            changed.add(name)
            if PROTECTED.search(name) or not any(name==entry or (entry.endswith("/") and name.startswith(entry)) for entry in allowed):
                raise ValueError("candidate history touched protected or unapproved path")
            entry=git(root,"ls-tree",commit,"--",name).strip()
            if entry and (entry.startswith("120000 ") or entry.startswith("160000 ")):
                raise ValueError("candidate history introduced symlink or submodule")
    objects=git(root,"rev-list","--objects",base+".."+head).splitlines()
    if len(objects)>MAX_OBJECTS:raise ValueError("candidate object count is outside policy")
    scanned_blobs=0
    for record in objects:
        object_id,_,name=record.partition(" ")
        if not SHA.fullmatch(object_id):raise ValueError("candidate object identity is invalid")
        if git(root,"cat-file","-t",object_id).strip()!="blob":continue
        size=int(git(root,"cat-file","-s",object_id).strip())
        if size>MAX_BLOB_BYTES:raise ValueError("candidate blob exceeds secret scan limit")
        content=git(root,"cat-file","blob",object_id,binary=True)
        if b"\0" in content:raise ValueError("binary candidate blob is not allowed")
        findings.extend(scanner.inspect("history",name or object_id,content));scanned_blobs+=1
    if findings:raise ValueError("secret pattern exists in candidate history")
    return {"status":"pass","base_sha":base,"head_sha":head,"commits":len(commits),"changed_paths":len(changed),"scanned_blobs":scanned_blobs,"objects":len(objects)}


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("root");parser.add_argument("base");parser.add_argument("head");parser.add_argument("--allowed",action="append",default=[]);args=parser.parse_args()
    print(json.dumps(verify(Path(args.root),args.base,args.head,args.allowed)))


if __name__=="__main__":main()
