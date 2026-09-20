# Control-plane image (AD-6): one-shot container, root context, runs as host user proxima-jobs (1010).
# Ships the repo Makefile + tools/ + uv project so `make apply-migrations` runs inside the container
# with owner secrets mounted as /run/secrets files (AD-11/AD-15); nothing is baked into the image.

FROM python:3.14-slim-bookworm AS builder
ENV UV_PYTHON_DOWNLOADS=never
WORKDIR /repo
RUN pip install --no-cache-dir uv==0.11.7
COPY services/control-plane/pyproject.toml services/control-plane/uv.lock ./services/control-plane/
# src/ is copied explicitly: a multi-source COPY would flatten its contents into the
# destination and hatchling's packages = ["src/..."] would build an empty wheel.
COPY services/control-plane/src ./services/control-plane/src
RUN uv sync --directory services/control-plane --python 3.14 --locked --no-install-project --no-dev --all-extras \
    # Non-editable install of the project itself: `uv run` at container start must find it
    # already satisfied and never rebuild (rebuild would need network for build deps).
    && uv pip install --python services/control-plane/.venv/bin/python --no-deps ./services/control-plane

FROM python:3.14-slim-bookworm AS runner
# UV_OFFLINE + UV_NO_SYNC: the morning job must not depend on PyPI. The venv from the
# builder stage already holds deps + the project itself; `uv run` must not resync/rebuild
# (rebuilding the editable target would fetch hatchling from the network).
ENV PATH="/app/services/control-plane/.venv/bin:/usr/local/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_OFFLINE=1 \
    UV_NO_SYNC=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1010 proxima-jobs && useradd --system --gid 1010 --create-home --home-dir /home/proxima-jobs --shell /usr/sbin/nologin proxima-jobs \
    && mkdir -p /app /work && chown -R 1010:1010 /app /work
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder --chown=1010:1010 /repo/services/control-plane/.venv ./services/control-plane/.venv
COPY --chown=1010:1010 services/control-plane/pyproject.toml services/control-plane/uv.lock ./services/control-plane/
COPY --chown=1010:1010 services/control-plane/src ./services/control-plane/src
COPY --chown=1010:1010 tools ./tools
COPY --chown=1010:1010 contracts ./contracts
COPY --chown=1010:1010 db ./db
# infra/jobs.env is NOT baked in: compose bind-mounts it (../infra/jobs.env:/app/infra/jobs.env:ro)
# so a host-side edit takes effect on the next `compose run` without an image rebuild.
COPY --chown=1010:1010 Makefile ./Makefile
USER 1010
# AD-6/AD-15 one-shot job container: the full command arrives from
# `docker compose run control-plane-admin make apply-migrations ENV_FILE=infra/jobs.env`.
WORKDIR /app
