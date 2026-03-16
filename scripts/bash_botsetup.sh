#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)
ENV_DIR="$PROJECT_ROOT/EnvHatsuneMiku"
VENV_PYTHON="$ENV_DIR/bin/python"

cd "$PROJECT_ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found in PATH."
  exit 1
fi

if [ ! -d "$ENV_DIR" ]; then
  echo "Creating virtual environment at $ENV_DIR"
  python3 -m venv "$ENV_DIR"
else
  echo "Virtual environment already exists at $ENV_DIR"
fi

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$PROJECT_ROOT/requirements.txt"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg was not found in PATH."
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Warning: node was not found in PATH."
fi

echo "Bot setup complete."
