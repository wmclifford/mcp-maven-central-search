ARG PYTHON_VERSION=3.12
ARG BASE_FLAVOR=alpine

FROM python:${PYTHON_VERSION}-${BASE_FLAVOR} AS builder

ARG BASE_FLAVOR

RUN set -eux; \
    if command -v apk >/dev/null 2>&1; then \
      apk add --no-cache curl ca-certificates; \
    else \
      apt-get update; \
      apt-get install -y --no-install-recommends curl ca-certificates; \
      rm -rf /var/lib/apt/lists/*; \
    fi

ENV UV_CACHE_DIR=/root/.cache/uv \
    PATH=/root/.local/bin:${PATH}
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

COPY pyproject.toml ./
COPY uv.lock ./

RUN uv sync --frozen --no-dev

COPY mcp_maven_central_search ./mcp_maven_central_search

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

FROM python:${PYTHON_VERSION}-${BASE_FLAVOR} AS runtime

ARG BASE_FLAVOR

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:${PATH}

WORKDIR /app

RUN set -eux; \
    if command -v apk >/dev/null 2>&1; then \
      addgroup -S app && adduser -S -G app app; \
    else \
      groupadd -r app && useradd -r -g app app; \
    fi

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/mcp_maven_central_search /app/mcp_maven_central_search
COPY pyproject.toml /app/pyproject.toml

RUN chown -R app:app /app

USER app

ENTRYPOINT ["python", "-c", "from mcp_maven_central_search.server import run; run()"]
