# syntax=docker/dockerfile:1.7

# ─── Builder stage ───────────────────────────────────────────────
# Pinned to digest of python:3.11-slim-bookworm for reproducibility.
# Refresh manually when bumping Python; never use `latest`.
FROM python:3.11.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# uv pinned (build determinism). Bump in lockstep with apps/api/pyproject.toml.
COPY --from=ghcr.io/astral-sh/uv:0.5.13 /uv /usr/local/bin/uv

# Build deps for native wheels (docling, transformers). Slim runtime image
# omits these.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Cache deps separately from source; rebuilds only when pyproject changes.
COPY pyproject.toml ./
COPY uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --no-install-project 2>/dev/null \
    || uv sync --no-dev --no-install-project

COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-editable --frozen 2>/dev/null \
    || uv sync --no-dev --no-editable

# ─── Runtime stage ───────────────────────────────────────────────
FROM python:3.11.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8100

# tini = PID 1 reaper; ca-certificates required for outbound TLS to Atlas/OpenAI.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        tini \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --home /app --shell /sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /opt/venv /opt/venv
COPY --chown=app:app src/ ./src/
COPY --chown=app:app pyproject.toml ./

USER app

EXPOSE 8100

# Healthcheck via stdlib urllib (no curl needed). Mirrors compose-level check.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8100/health',timeout=5).status==200 else 1)" \
    || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8100"]
