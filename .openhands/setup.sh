#!/bin/bash
# Runs every time OpenHands opens this repository in a sandbox.
# Toolchain contract: Node >=22 <23, uv + Python 3.14, npm workspaces.
set -euo pipefail
cd "${OPENHANDS_PROJECT_DIR:-$PWD}"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.14

node --version
export PUPPETEER_SKIP_DOWNLOAD=1
npm ci --no-audit --no-fund

make codegen
