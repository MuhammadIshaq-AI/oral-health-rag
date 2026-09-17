# DentalCare AU API (CPU image; mount ./data for the index, logs and models).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/models/hf

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project \
        --extra ml --extra ingest --extra stt --extra tts --extra anthropic

COPY api ./api
COPY ingest ./ingest
COPY eval ./eval
COPY prompts ./prompts
COPY configs ./configs
RUN uv sync --frozen --no-dev \
        --extra ml --extra ingest --extra stt --extra tts --extra anthropic

RUN useradd --create-home --uid 1000 app && mkdir -p /app/data /models/hf && chown -R app /app/data /models
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--app-dir", "api", "--host", "0.0.0.0", "--port", "8000"]
