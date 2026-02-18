#!/bin/bash
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." &>/dev/null && pwd)
if [ -d "$SCRIPT_DIR/EnvHatsuneMiku" ]; then
  echo "Virtual environment already exists."
else
  python3 -m venv "$SCRIPT_DIR/EnvHatsuneMiku"
  source "$SCRIPT_DIR/EnvHatsuneMiku/bin/activate"
  pip install -r requirements.txt
fi
