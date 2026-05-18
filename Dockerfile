FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  UV_PROJECT_ENVIRONMENT=/app/.venv \
  PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  ffmpeg \
  libopus0 \
  nodejs \
  && rm -rf /var/lib/apt/lists/*


RUN python -m pip install --upgrade pip uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

RUN mkdir -p /app/logs /app/data


CMD ["hatsune-miku-bot", "--docker"]
