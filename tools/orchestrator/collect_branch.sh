#!/bin/bash
# collect_branch.sh <conversation-id> <branch> <base-ref> <out-bundle>
# Packs the worker's commits into a bundle the conductor can inspect and push.
set -uo pipefail
. "$(dirname "$0")/lib.sh"
CID="${1:?conversation id}"; BRANCH="${2:?branch}"; BASE="${3:?base ref}"; OUT="${4:?out bundle}"
REPO="$(workspace_repo "$CID")"
G() { git -C "$REPO" -c safe.directory='*' "$@"; }
[ -d "$REPO/.git" ] || { echo "no checkout for $CID" >&2; exit 2; }
DIRTY="$(G status --short | grep -cv '^??' || echo 0)"
[ "$DIRTY" = "0" ] || echo "warning: $DIRTY tracked files uncommitted in $REPO" >&2
COUNT="$(G log --oneline "$BASE..$BRANCH" 2>/dev/null | wc -l | tr -d ' ')"
[ "$COUNT" != "0" ] || { echo "no commits on $BRANCH above $BASE" >&2; exit 3; }
rm -f "$OUT"
G bundle create "$OUT" "$BASE..$BRANCH" >/dev/null 2>&1 || { echo "bundle failed" >&2; exit 3; }
chmod 644 "$OUT"
log_json collect "$BRANCH: $COUNT commits"
echo "$COUNT"
