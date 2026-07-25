FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  UV_PROJECT_ENVIRONMENT=/app/.venv \
  UV_LINK_MODE=copy

WORKDIR /app

RUN python -m pip install "uv==0.11.3"

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --extra prometheus --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --extra prometheus

FROM debian:trixie-slim AS quickjs-builder

ARG QUICKJS_VERSION=2026-06-04
ARG QUICKJS_SHA256=b376e839b322978313d929fd20663b11ba58b75df5a46c126dd19ea2fa70ad2a

# Make every pipeline fail when any command in it fails, not only the last one.
# This is required for the checksum verification pipeline below (DL4006).
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# The build dependencies remain in this disposable stage.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  ca-certificates \
  curl \
  xz-utils \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/quickjs

RUN curl --fail --show-error --silent --location \
  "https://bellard.org/quickjs/quickjs-${QUICKJS_VERSION}.tar.xz" \
  --output quickjs.tar.xz \
  && echo "${QUICKJS_SHA256}  quickjs.tar.xz" | sha256sum --check --strict \
  && tar --extract --file quickjs.tar.xz --strip-components=1 \
  && make -j"$(nproc)" qjs \
  && strip qjs

FROM mwader/static-ffmpeg:8.1.2@sha256:33f770f812cbfc3de96c547157fc9faf8bd95a36481753439ffa761045167585 AS ffmpeg

FROM python:3.14-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Debian security repositories replace package revisions over time, so exact
# apt versions would make rebuilds fail once an older revision is removed.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  libopus0 \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd --gid 10001 bot \
  && useradd --uid 10001 --gid bot --no-create-home \
  --home-dir /nonexistent --shell /usr/sbin/nologin bot

COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=quickjs-builder /tmp/quickjs/qjs /usr/local/bin/qjs
COPY --from=builder /app/.venv ./.venv
COPY src ./src
RUN qjs -e 'console.log("QuickJS runtime ready")' \
  && ffmpeg -hide_banner -version \
  && install -d --owner=bot --group=bot --mode=0750 /app/logs /app/data \
  && install -d --mode=1777 /tmp

# The application and dependencies remain root-owned and read-only to the
# unprivileged runtime process. Logs and data are private to the bot, while
# /tmp remains writable with the sticky bit for QuickJS and other subprocesses.
USER 10001:10001

# You can change the output of the logs to "color" if you prefer more
# humanreadble logs
# You can remove --prometheus_enabled and --extra prometheus if prefer
# a smaller container with less logging/metrics
CMD ["hatsune-miku-bot", "--prod_enabled", "--json_logging", "--prometheus_enabled"]
