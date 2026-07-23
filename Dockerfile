FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  UV_PROJECT_ENVIRONMENT=/app/.venv \
  PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Debian security repositories replace package revisions over time, so exact
# apt versions would make rebuilds fail once an older revision is removed.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  ffmpeg \
  libopus0 \
  nodejs \
  && rm -rf /var/lib/apt/lists/* \
  && python -m pip install "uv==0.11.3"

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev \
  && mkdir -p /app/logs /app/data

# You can change the output of the logs to "color" if you pefer more
# humanreadble logs
CMD ["hatsune-miku-bot", "--prod_enabled", "--json_logging"]
