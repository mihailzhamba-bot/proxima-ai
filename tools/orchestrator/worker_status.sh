#!/bin/bash
# worker_status.sh <conversation-id> [...]
# One line per worker: id, execution status, event count, branch, dirty files.
set -uo pipefail
. "$(dirname "$0")/lib.sh"
for CID in "$@"; do
  REPO="$(workspace_repo "$CID")"
  BRANCH="$(git -C "$REPO" -c safe.directory='*' branch --show-current 2>/dev/null || echo -)"
  DIRTY="$(git -C "$REPO" -c safe.directory='*' status --short 2>/dev/null | grep -cv '^??' || echo 0)"
  printf '%s status=%s events=%s branch=%s dirty=%s\n' \
    "${CID:0:8}" "$(conversation_status "$CID")" "$(conversation_events "$CID")" "$BRANCH" "$DIRTY"
done
