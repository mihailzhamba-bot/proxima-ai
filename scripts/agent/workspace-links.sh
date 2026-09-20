#!/usr/bin/env bash
# workspace-links.sh — идемпотентно расставляет симлинки приватных путей (ops-репо)
# в композитном рабочем дереве:  proxima-ai/  +  proxima-ai-ops/  рядом.
# Публичное дерево никогда не трекает эти пути (.gitignore закрыт навсегда, D40).
set -euo pipefail
cd "$(dirname "$0")/../.."

OPS_DIR="${OPS_DIR:-../proxima-ai-ops}"

if [ ! -d "$OPS_DIR" ]; then
  echo "workspace-links: FAIL: $OPS_DIR не найден."
  echo "Клонируй proxima-ai-ops рядом с этим чекаутом (sibling) и перезапусти,"
  echo "или задай OPS_DIR=/путь/к/proxima-ai-ops."
  exit 1
fi

make_link() { # make_link <link-path> <target-inside-ops>
  local link="$1" target="$OPS_DIR/$2"
  if [ -L "$link" ]; then
    local current
    current="$(readlink "$link")"
    if [ "$current" = "$target" ]; then
      echo "workspace-links: ok (already): $link"
      return 0
    fi
    echo "workspace-links: replace stale link $link -> $target"
    rm "$link"
  elif [ -e "$link" ]; then
    echo "workspace-links: FAIL: $link существует и не симлинк - освободи путь вручную." >&2
    exit 1
  fi
  ln -s "$target" "$link"
  echo "workspace-links: linked: $link -> $target"
}

make_link "docs" "docs"
make_link "_bmad-output" "_bmad-output"
make_link "_bmad" "_bmad"
make_link ".agents" ".agents"
make_link ".opencode" ".opencode"
make_link ".claude" ".claude"
make_link ".codex" ".codex"
make_link "STATE.md" "STATE.md"
make_link "DECISIONS.md" "DECISIONS.md"
make_link "ARCHITECTURE.md" "ARCHITECTURE.md"
make_link "CLAUDE.md" "CLAUDE.md"
make_link "CHANGELOG.md" "CHANGELOG.md"

echo "workspace-links: DONE (композит готов: docs из $OPS_DIR)"
