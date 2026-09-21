"""Trusted no-exec gate. Parent alone owns the write end of the permission pipe."""
import os
import sys


def main():
    descriptor = int(sys.argv[1])
    command = sys.argv[2:]
    try:
        permission = os.read(descriptor, 1)
    finally:
        os.close(descriptor)
    # Parent death closes its sole write descriptor. EOF must never run git.
    if permission != b"R" or not command:
        raise SystemExit(125)
    try:
        os.execvpe(command[0], command, os.environ)
    except OSError:
        raise SystemExit("publisher command could not start") from None


if __name__ == "__main__":
    main()
