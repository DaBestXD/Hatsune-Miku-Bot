#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)
SETUP_SCRIPT="$PROJECT_ROOT/scripts/bash_botsetup.sh"

cd "$PROJECT_ROOT"

if ! command -v uv >/dev/null 2>&1 || [ ! -d "$PROJECT_ROOT/.venv" ]; then
  echo "uv environment not ready. Running setup first."
  bash "$SETUP_SCRIPT"
fi
uv run python -m yt_dlp --remote-components ejs:github --version >/dev/null
exec uv run hatsune-miku-bot "$@"
