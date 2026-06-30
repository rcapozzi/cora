# --- Stage 0: Bootstrap a proper venv so we can at least satisfy local CLI deps in this env ---
#FROM python:3.14-slim AS ops
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS ops
# RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
#     && rm -rf /var/lib/apt/lists/* \
#     && python -m pip install --no-cache-dir 'uv>=0.5'

# --- Stage 1: Build & Install Deps Into a Fast, Reusable venv ---
FROM ops AS build
WORKDIR /build
COPY pyproject.toml uv.lock ./
# Use `uv sync` -D: the UV venv writer knows not to walk into immutability-driven recursive refs.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- Stage 2: Package That venv Into a Final _workingapp_ Base For The Web Service ---
FROM ops AS runtime
WORKDIR /app

# Make the venv we build inside /app actually resolvable in the final image.
COPY --from=build /build/.venv /app/.venv

# Make Python prefer site-packages over a venv directory (uv in build mode created /build/.venv, but production image will not have /build).
ENV VIRTUAL_ENV=/app/.venv
ENV PATH=/app/.venv/bin:$PATH

# Copy the actual source in after validation so we do not invalidate layers unless code changes.
COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
