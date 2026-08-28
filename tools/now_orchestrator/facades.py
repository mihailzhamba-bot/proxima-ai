from __future__ import annotations

from .core import Snapshot, render, select


def _entry(snapshot: Snapshot) -> str:
    return render(select(snapshot))


def claude_entry(snapshot: Snapshot) -> str:
    return _entry(snapshot)


def codex_entry(snapshot: Snapshot) -> str:
    return _entry(snapshot)


def opencode_entry(snapshot: Snapshot) -> str:
    return _entry(snapshot)


FACADE_ENTRIES = {"claude": claude_entry, "codex": codex_entry, "opencode": opencode_entry}

__all__ = ["FACADE_ENTRIES", "claude_entry", "codex_entry", "opencode_entry"]
