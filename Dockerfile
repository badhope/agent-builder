# syntax=docker/dockerfile:1.7
# ---------- Stage 1: build a virtualenv ----------
FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    libheif-dev \
    libpango1.0-dev \
    libcairo2-dev \
    pkg-config \
    rustc \
    cargo \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip wheel setuptools

COPY backend/ /build/backend/
RUN /opt/venv/bin/pip install --no-cache-dir -e .

# ---------- Stage 2: runtime ----------
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

# System packages required by the converters at runtime.
# LibreOffice / Pandoc / Tesseract are large — they live in a separate
# "converters" image (see deploy/Dockerfile.converters). This image only
# carries minimal system libs for the Python side.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tini \
    libpq5 \
    libxml2 \
    libxslt1.1 \
    libffi8 \
    libssl3 \
    zlib1g \
    libjpeg62-turbo \
    libpng16-16 \
    libtiff6 \
    libwebp7 \
    libheif1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    fonts-liberation \
    fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --shell /bin/bash --uid 1000 app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app backend/ /app/backend/
COPY --chown=app:app pyproject.toml /app/pyproject.toml
COPY --chown=app:app entrypoints/ /app/entrypoints/
WORKDIR /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoints/entrypoint.sh"]
CMD ["api"]
