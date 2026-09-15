#!/usr/bin/python3 -I
"""Admit an exact candidate only with a separate root-owned review receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

RECEIPTS = Path('/etc/loop-review/receipts')


def diff_digest(root: Path, base: str, head: str) -> str:
    if any(not re.fullmatch(r'[0-9a-f]{40}', value) for value in [base, head]):
        raise ValueError('invalid review SHA')
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/var/empty', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_OPTIONAL_LOCKS': '0'}
    def git(*args):
        return subprocess.check_output(['/usr/bin/git', '-c', 'core.hooksPath=/dev/null',
            '-C', str(root), *args], env=env, stderr=subprocess.DEVNULL, timeout=30)
    if git('rev-parse', 'HEAD').decode().strip() != head:
        raise ValueError('candidate head changed')
    git('merge-base', '--is-ancestor', base, head)
    if git('status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('candidate tracked files changed')
    return hashlib.sha256(git('diff', '--no-ext-diff', '--no-textconv', '--binary', base, head, '--')).hexdigest()


def validate_receipt(path: Path, base: str, head: str, digest: str, owner: int = 0) -> dict:
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != owner or info.st_mode & 0o022:
            raise ValueError('untrusted receipt directory')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd) as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != owner or info.st_mode & 0o022 or info.st_nlink != 1 or info.st_size > 65536:
            raise ValueError('untrusted review receipt')
        receipt = json.load(handle)
    if (receipt.get('base_sha'), receipt.get('sha'), receipt.get('diff_sha256')) != (base, head, digest):
        raise ValueError('review scope mismatch')
    if receipt.get('status') != 'pass' or type(receipt.get('skipped')) is not int or receipt['skipped'] != 0:
        raise ValueError('review did not pass')
    if any(not isinstance(receipt.get(key), str) or not receipt[key].strip() for key in ['reviewer', 'reviewed_at_utc', 'evidence_ref']):
        raise ValueError('review evidence missing')
    return {'sha': head, 'status': 'pass', 'skipped': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fingerprint', action='store_true')
    parser.add_argument('--wait-seconds', type=int, default=0)
    parser.add_argument('checkout', type=Path)
    parser.add_argument('base')
    parser.add_argument('head')
    args = parser.parse_args()
    digest = diff_digest(args.checkout, args.base, args.head)
    if args.fingerprint:
        print(json.dumps({'base_sha': args.base, 'sha': args.head, 'diff_sha256': digest, 'status': 'pending'}))
        return
    deadline = time.monotonic() + min(max(args.wait_seconds, 0), 1800)
    while True:
        try:
            result = validate_receipt(RECEIPTS / (args.head + '.json'), args.base, args.head, digest)
            if diff_digest(args.checkout, args.base, args.head) != digest:
                raise ValueError('candidate changed during review')
            print(json.dumps(result)); return
        except FileNotFoundError:
            if time.monotonic() >= deadline: raise ValueError('independent review receipt missing') from None
            time.sleep(2)


if __name__ == '__main__':
    try: main()
    except Exception:
        print(json.dumps({'status': 'blocked', 'reason': 'independent exact-SHA review absent or invalid'}))
        raise SystemExit(1)
