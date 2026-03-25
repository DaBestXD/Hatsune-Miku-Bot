FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  ffmpeg \
  libopus0 \
  nodejs \
  && rm -rf /var/lib/apt/lists/*


COPY requirements.txt ./

RUN python -m pip install --upgrade pip \
  && python -m pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/data


CMD ["python", "hatsune_miku_bot/main.py", "--docker"]
