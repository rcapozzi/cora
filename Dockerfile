FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS build

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
      --frozen --no-dev --no-install-project --compile-bytecode

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

ENV \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY --from=build /app /app

RUN useradd --create-home web
USER web

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]