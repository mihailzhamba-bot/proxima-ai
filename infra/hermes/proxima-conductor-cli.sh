#!/bin/bash
# SSH forced command for the Hermes brain. The client can pass only a verb and
# validated arguments; everything else is refused. Runs as openhands-agent.
set -uo pipefail
umask 077

CLI=/srv/proxima-ai/conductor-repo-checkout/tools/orchestrator/conductor_cli.py
LOG=/srv/proxima-ai/conductor/cli.log
export CONDUCTOR_REPO_CHECKOUT=/srv/proxima-ai/conductor-repo-checkout
export CONDUCTOR_STATE_DIR=/srv/proxima-ai/conductor

deny() { printf '{"ok":false,"error":"%s"}\n' "$1"; exit 1; }

RAW="${SSH_ORIGINAL_COMMAND:-}"
[ -n "$RAW" ] || deny "empty command"
# no shell metacharacters at all: the client sends a plain verb line
case "$RAW" in
  *[\;\|\&\$\`\<\>]*) deny "illegal characters" ;;
esac

set -- $RAW
VERB="${1:-}"; shift || true

case "$VERB" in
  status|queue|stop|start|poll|report)
    [ "$#" -eq 0 ] || deny "$VERB takes no arguments"
    ;;
  go|skip)
    [ "$#" -eq 1 ] || deny "$VERB needs exactly one story id"
    echo "$1" | grep -Eq '^[0-9]+\.[0-9]+$' || deny "bad story id"
    ;;
  dispatch)
    [ "$#" -ge 1 ] || deny "dispatch needs a story id"
    echo "$1" | grep -Eq '^[0-9]+\.[0-9]+$' || deny "bad story id"
    if [ "$#" -eq 3 ]; then
      [ "$2" = "--profile" ] || deny "only --profile is allowed"
      case "$3" in fedor|glm) : ;; *) deny "unknown profile" ;; esac
    elif [ "$#" -ne 1 ]; then
      deny "bad dispatch arguments"
    fi
    ;;
  answer)
    # answer <story> <base64-text>: free text is base64 so it cannot carry syntax
    [ "$#" -eq 2 ] || deny "answer needs a story id and base64 text"
    echo "$1" | grep -Eq '^[0-9]+\.[0-9]+$' || deny "bad story id"
    echo "$2" | grep -Eq '^[A-Za-z0-9+/=]+$' || deny "text must be base64"
    TEXT="$(printf '%s' "$2" | base64 -d 2>/dev/null)" || deny "bad base64"
    [ ${#TEXT} -le 4000 ] || deny "answer too long"
    printf '%s conductor-cli answer %s\n' "$(date -u +%FT%TZ)" "$1" >>"$LOG" 2>/dev/null
    exec python3 "$CLI" answer "$1" "$TEXT"
    ;;
  *)
    deny "verb not allowed: $VERB"
    ;;
esac

printf '%s conductor-cli %s %s\n' "$(date -u +%FT%TZ)" "$VERB" "$*" >>"$LOG" 2>/dev/null
exec python3 "$CLI" "$VERB" "$@"
