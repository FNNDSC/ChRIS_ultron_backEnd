# Benchmark harness image. The package source is bind-mounted at /app/benchmarks by the
# compose override, so this image only needs Python and the harness dependencies.
#
# The base is digest-pinned rather than tag-pinned: `python:3.12-slim` is a rolling tag,
# and a harness whose job is to produce comparable numbers over time must not drift
# underneath its own results. Refresh this deliberately, on the same cadence as the UBI
# tag bump in the root Dockerfile.
FROM docker.io/library/python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /usr/local/bin/

# Install into the image's system Python so `python -m benchmarks.run_bench` works with no
# PATH change, and so the /app/benchmarks bind mount cannot shadow a project-local .venv.
# UV_LINK_MODE=copy because uv's cache (a cache mount below) and /usr/local are on
# different filesystems, where uv cannot hardlink.
ENV UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
# pyproject.toml and uv.lock are bind-mounted and uv's cache is a cache mount, as at the
# same step of the root Dockerfile (Podman must be 5.4 or above: see `just check-builder`).
# The sync runs as root, so the cache sits at uv's default location for root. The dev
# group carries pytest, which `just bench-test` runs inside this image.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked

# Drop root in the image; the compose override sets `user:`/`group_add` at runtime so the
# socket-mounted benchmark service can still sample stats and reap job containers
# (see docker-compose.benchmark.yml).
USER nobody

# Default command is informational; `just bench-run` overrides it with the real CLI.
CMD ["python", "-m", "benchmarks.run_bench", "--help"]
