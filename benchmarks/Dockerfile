# Benchmark harness image. The package source is bind-mounted at /app/benchmarks by the
# compose override, so this image only needs Python and the harness dependencies.
#
# The base is digest-pinned rather than tag-pinned: `python:3.12-slim` is a rolling tag,
# and a harness whose job is to produce comparable numbers over time must not drift
# underneath its own results. Refresh this deliberately, on the same cadence as the UBI
# tag bump in the root Dockerfile.
FROM docker.io/library/python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

COPY --from=ghcr.io/astral-sh/uv:0.12.11 /uv /uvx /usr/local/bin/

# Install into the image's system Python so `python -m benchmarks.run_bench` works with no
# PATH change, and so the /app/benchmarks bind mount cannot shadow a project-local .venv.
ENV UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
# The dev group carries pytest, which `just bench-test` runs inside this image.
RUN uv sync --locked

# Drop root in the image; the compose override sets `user:`/`group_add` at runtime so the
# socket-mounted benchmark service can still sample stats and reap job containers
# (see docker-compose.benchmark.yml).
USER nobody

# Default command is informational; `just bench-run` overrides it with the real CLI.
CMD ["python", "-m", "benchmarks.run_bench", "--help"]
