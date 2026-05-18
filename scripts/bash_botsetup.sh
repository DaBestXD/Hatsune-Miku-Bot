#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)

cd "$PROJECT_ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv was not found in PATH. Install it from https://docs.astral.sh/uv/ and rerun this script."
  exit 1
fi

uv sync

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg was not found in PATH."
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Warning: node was not found in PATH."
fi

echo "Bot setup complete."
