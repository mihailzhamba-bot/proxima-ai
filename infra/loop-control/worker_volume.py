#!/usr/bin/python3 -I
"""Mount and verify the bounded Claudette LOOP workspace filesystem."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import subprocess


IMAGE=Path("/var/lib/loop-worker-volume.img")
TARGET=Path("/srv/loop-worker")
MAX_BYTES=8*1024**3
MIN_FREE_BYTES=512*1024**2


def mounted() -> bool:
    return subprocess.run(["/usr/bin/mountpoint","-q",str(TARGET)]).returncode==0


def validate_mount_metadata(source: str,filesystem: str,raw_options: str,loops: str) -> None:
    if not source.startswith("/dev/loop") or not any(line.startswith(source+":") for line in loops.splitlines()):raise RuntimeError("worker mount is not backed by the approved image")
    options=set(raw_options.split(","))
    if filesystem!="ext4" or not {"rw","nodev","nosuid","noatime"}.issubset(options):raise RuntimeError("worker mount filesystem or options are unsafe")


def validate() -> None:
    info=IMAGE.lstat()
    if not stat.S_ISREG(info.st_mode) or IMAGE.is_symlink() or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size!=MAX_BYTES:
        raise RuntimeError("bounded worker image is invalid")
    if not mounted():raise RuntimeError("bounded worker filesystem is not mounted")
    mount_fields=subprocess.check_output(["/usr/bin/findmnt","-n","-o","SOURCE,FSTYPE,OPTIONS","--target",str(TARGET)],text=True).strip().split(maxsplit=2)
    if len(mount_fields)!=3:raise RuntimeError("worker mount metadata is incomplete")
    source,filesystem,raw_options=mount_fields
    loops=subprocess.check_output(["/usr/sbin/losetup","-j",str(IMAGE)],text=True)
    validate_mount_metadata(source,filesystem,raw_options,loops)
    usage=shutil.disk_usage(TARGET)
    if usage.total>MAX_BYTES+128*1024**2 or usage.free<MIN_FREE_BYTES:raise RuntimeError("bounded worker filesystem capacity gate failed")


def mount() -> None:
    if not mounted():subprocess.run(["/usr/bin/mount","-o","loop,nodev,nosuid,noatime",str(IMAGE),str(TARGET)],check=True)
    validate()


def unmount() -> None:
    if mounted():subprocess.run(["/usr/bin/umount",str(TARGET)],check=True)


def main() -> None:
    parser=argparse.ArgumentParser();actions=parser.add_mutually_exclusive_group(required=True);actions.add_argument("--mount",action="store_true");actions.add_argument("--check",action="store_true");actions.add_argument("--unmount",action="store_true");args=parser.parse_args()
    if args.mount:mount()
    elif args.check:validate()
    else:unmount()


if __name__=="__main__":main()
