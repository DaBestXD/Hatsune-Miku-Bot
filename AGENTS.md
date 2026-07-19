# HATSUNE-MIKU-BOT

## Project notes

1. Do not edit anything under src/ unless asked to by user.
2. After editing code run:
    - `uv run ty check`
    - `uv run ty check --error all`
      - Ignore any errors for typing overloads for build in python dunder methods
    - `uv run  ruff format`
    - `uv run ruff check --fix`
    - `uv run pytest`
