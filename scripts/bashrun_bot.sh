#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)
ENV_DIR="$PROJECT_ROOT/EnvHatsuneMiku"
VENV_PYTHON="$ENV_DIR/bin/python"
SETUP_SCRIPT="$PROJECT_ROOT/scripts/bash_botsetup.sh"

cd "$PROJECT_ROOT"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Virtual environment not found. Running setup first."
  bash "$SETUP_SCRIPT"
fi
"$VENV_PYTHON" -m pip install -U yt-dlp
"$VENV_PYTHON" -m yt_dlp --remote-components ejs:github --version >/dev/null
exec "$VENV_PYTHON" "$PROJECT_ROOT/main.py" "$@"
