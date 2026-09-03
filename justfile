# This is a `justfile` for the development of ChRIS backend. For the most part,
# it is a wrapper around the `docker compose` or `podman compose` command.
# Use the `just` program to execute `justfile` commands. Run
#
#     just -l
#
# to list commands and their descriptions.
#
# The syntax and usage of `justfile` is similar to Makefile of GNU Make.
# For more information, see https://just.systems/man/en/chapter_1.html

# Storage mode: "fslink" (default), "swift" (Swift object storage), or "s3" (S3-compatible storage).
# Usage: just storage=swift dev
# Or persist the preference: just set-storage swift
storage := `if [ -f '.storage' ]; then cat .storage; else echo fslink; fi`

# Whether `compose run` should allocate a TTY, auto-detected from stdin.
# Interactive recipes (`just bash`, `just shell`) need one; non-interactive
# callers such as CI must not have one -- under `podman compose` on the GitHub
# Actions runner, allocating a TTY makes `compose run` hang forever after the
# image build. Force it off with `just tty=false ...`.
tty := `if [ -t 0 ]; then echo true; else echo false; fi`

# Start the ChRIS backend in development mode, and attach to the live-reloading server.
[group('(1) start-up')]
dev: chrisomatic attach

# Start the ChRIS backend in development mode.
[group('(1) start-up')]
start: start-ancillary migrate up

# Start services (without running database migrations).
[group('(1) start-up')]
up: (docker-compose '--profile=cube up -d')

# Attach to the chris container.
[group('(3) development')]
attach: (docker-compose '--profile=cube attach chris | grep -Fv "\"GET /api/v1/users/ HTTP/1.1\" 200"')

# Open a Python shell.
[group('(3) development')]
shell: (run 'python manage.py shell')

# Open a Bash shell.
[group('(3) development')]
bash: (run 'bash')

# Run chrisomatic, a tool which adds plugins and users to CUBE.
[group('(1) start-up')]
chrisomatic *args: start
    @just storage={{ storage }} docker-compose --profile=cube run --rm chrisomatic chrisomatic {{ args }}

# Run chrisomatic with the contents of chrisomatic/postscript.yml
[group('(1) start-up')]
postscript: (chrisomatic 'postscript.yml')

# Perform database migrations.
[group('(1) start-up')]
migrate: (run 'python manage.py migrate --noinput')

# Create database migrations.
[group('(3) development')]
makemigrations: (run 'python manage.py makemigrations')

# Run tests, e.g. `just test pacsfiles`
[group('(3) development')]
test *args:
    @just storage={{ storage }} run python manage.py test --force-color {{ args }}

# Run all tests.
[group('(3) development')]
test-all: test-unit test-integration

# Run unit tests.
[group('(3) development')]
test-unit: start-ancillary (run 'python manage.py test --force-color --exclude-tag integration')

# Run integration tests.
[group('(3) development')]
test-integration: start-ancillary (run 'python manage.py test --force-color --tag integration')

# Run the full test suite under coverage and print a report.
[group('(3) development')]
test-coverage: start-ancillary
    @just storage={{ storage }} run coverage erase
    @just storage={{ storage }} run coverage run manage.py test --force-color
    @just storage={{ storage }} run coverage report

# Run unit tests under coverage and write a Cobertura XML report to chris_backend/coverage.xml.
[group('(3) development')]
test-unit-coverage: start-ancillary
    @just storage={{ storage }} run coverage erase
    @just storage={{ storage }} run coverage run manage.py test --force-color --exclude-tag integration
    @just storage={{ storage }} run coverage xml

# Start dependency services.
[group('(1) start-up')]
start-ancillary: (docker-compose 'up -d')

# Stop services.
[group('(2) shutdown')]
down: (docker-compose '--profile=cube --profile=tools down')

# Stop services and remove all data.
[group('(2) shutdown')]
nuke: reap-plugin-instances (docker-compose '--profile=cube --profile=tools down -v --remove-orphans')

# Remove all plugin instance containers.
[group('(2) shutdown')]
reap-plugin-instances: (docker-compose 'run --rm pfcon python -c' '''
        '
        import os
        import docker
        d = docker.from_env()
        filters = {"label": os.getenv("JOB_LABELS")}
        containers = d.containers.list(all=True, filters=filters)
        for container in containers:
            print(f"Removing container: {container.name} ({container.image})", flush=True)
            container.remove(force=True)
        '
    ''')

# (Re-)build the container image.
[group('(4) docker-compose')]
build: (docker-compose '--profile=cube build')

# Pull container images.
[group('(4) docker-compose')]
pull: (docker-compose 'pull')

# Get container logs.
[group('(4) docker-compose')]
logs *args:
    @just storage={{ storage }} docker-compose --profile=cube logs {{ args }}

# docker-compose ... run helper function.
[group('(4) docker-compose')]
run +command:
    @just storage={{ storage }} docker-compose --profile=cube run --rm {{ if tty == "false" { "-T" } else { "" } }} chris {{ command }}

# docker-compose ... helper function.
[group('(4) docker-compose')]
docker-compose +command:
    env UID=$(id -u) GID=$(id -g) DOCKER_SOCK="$(just get-socket)" $(just get-engine) compose {{ if storage == "swift" { "-f docker-compose.yml -f docker-compose_swift.yml" } else if storage == "s3" { "-f docker-compose.yml -f docker-compose_s3.yml" } else { "" } }} {{ command }}

# Get the container engine to use (docker or podman)
[group('helper function')]
get-engine:
    @if [ -f '.preference' ]; then           \
      cat .preference && exit 0;             \
    elif type podman > /dev/null 2>&1; then  \
      echo podman;                           \
    else                                     \
      echo docker;                           \
    fi                                       \

# Get the docker daemon socket path.
[group('helper function')]
get-socket:
    @if [ "$(just get-engine)" = 'podman' ]; then     \
      just get-podman-socket;                         \
    else                                              \
      echo '/var/run/docker.sock';                    \
    fi

# Get the podman daemon socket path.
[group('helper function')]
get-podman-socket: check-podman-socket
    @podman info --format '{{{{ .Host.RemoteSocket.Path }}'

# Ensure that the podman daemon is running.
[group('helper function')]
check-podman-socket:
    @if [ "$(podman info --format '{{{{ .Host.RemoteSocket.Exists }}')" != 'true' ]; then   \
      cmd='systemctl --user start podman.service';                                          \
      >&2 echo "Podman daemon not running. Please run \`$(tput bold)$cmd$(tput sgr0)\`";    \
      exit 1;                                                                               \
    fi

# Set a preference for using either Docker or Podman.
[group('(5) docker/podman preference')]
prefer docker_or_podman:
    @[ '{{ docker_or_podman }}' = 'docker' ] || [ '{{ docker_or_podman }}' = 'podman' ] \
        || ( \
            >&2 echo 'argument must be either "docker" or "podman"'; \
            exit 1 \
        )
    echo '{{ docker_or_podman }}' > .preference

# Remove your preference for Docker or Podman.
[group('(5) docker/podman preference')]
unset-preference:
    rm -f .preference

# Set a preference for storage mode ("fslink", "swift", or "s3").
[group('(5) docker/podman preference')]
set-storage mode:
    @[ '{{ mode }}' = 'fslink' ] || [ '{{ mode }}' = 'swift' ] || [ '{{ mode }}' = 's3' ] \
        || ( \
            >&2 echo 'argument must be "fslink", "swift", or "s3"'; \
            exit 1 \
        )
    echo '{{ mode }}' > .storage

# Remove your preference for storage mode.
[group('(5) docker/podman preference')]
unset-storage:
    rm -f .storage

# Compose helper for the benchmark stack (fslink + uvicorn-envelope override).
[group('(6) benchmarks')]
bench-compose +command:
    env UID=$(id -u) GID=$(id -g) DOCKER_SOCK="$(just get-socket)" \
        DOCKER_GID="$(stat -c '%g' "$(just get-socket)" 2>/dev/null || stat -f '%g' "$(just get-socket)" 2>/dev/null || echo 0)" \
        COMPOSE_PROJECT_NAME="$(basename "$(pwd)" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9_-')" \
        GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)" \
        GIT_DIRTY="$(git diff --quiet HEAD 2>/dev/null && echo false || echo true)" \
        $(just get-engine) compose -f docker-compose.yml -f docker-compose.benchmark.yml {{ command }}

# Start the benchmark stack (fslink + uvicorn envelope), migrate, and register plugins.
[group('(6) benchmarks')]
bench-start:
    just bench-compose 'up -d --build db dragonflydb nats pfcon cube-nonroot-user-volume-fix'
    just bench-compose 'run --rm chris python manage.py migrate --noinput'
    just bench-compose 'up -d --build chris worker-mains worker-periodic celery-scheduler'
    just bench-compose '--profile cube run --rm chrisomatic chrisomatic'

# Run the benchmark harness, e.g. `just bench-run --tier smoke` or `just bench-run --tier full`.
[group('(6) benchmarks')]
bench-run *args:
    just bench-compose '--profile cube --profile bench build benchmark'
    just bench-compose '--profile cube --profile bench run --rm benchmark python -m benchmarks.run_bench {{ args }}'

# Run the harness unit tests inside the benchmark image.
[group('(6) benchmarks')]
bench-test *args:
    just bench-compose '--profile cube --profile bench build benchmark'
    just bench-compose '--profile cube --profile bench run --rm --no-deps benchmark python -m pytest -p no:cacheprovider benchmarks/tests {{ args }}'

# Control-plane RED load test (Locust). Args pass through, e.g.
# `just bench-locust '-u 100 -r 20 -t 3m'`. CSVs land in benchmarks/results/locust/.
[group('(6) benchmarks')]
bench-locust *args:
    just bench-compose '--profile cube --profile bench build benchmark'
    mkdir -p benchmarks/results/locust
    just bench-compose '--profile cube --profile bench run --rm benchmark locust -f benchmarks/locustfile.py --headless --csv /app/benchmarks/results/locust/run {{ args }}'

# Re-render a report from a results run id, e.g. `just bench-report 2026-06-09T153000Z`.
[group('(6) benchmarks')]
bench-report run_id:
    just bench-compose '--profile cube --profile bench run --rm --no-deps benchmark python -m benchmarks.report /app/benchmarks/results/{{ run_id }}'

# Compare runs over time: first = baseline, last = candidate, 3+ adds a trend table.
# Run ids resolve against results/ and the committed history/ archive, e.g.
# `just bench-compare 2026-06-09T153000Z 2026-06-10T214526Z --fail-on-regression`.
[group('(6) benchmarks')]
bench-compare *args:
    just bench-compose '--profile cube --profile bench run --rm --no-deps benchmark python -m benchmarks.compare {{ args }}'

# Keep a run's small artifacts (summary, levels, environment, rendered report) in
# version control so there is a human-readable history to compare against, e.g.
# `just bench-archive 2026-06-10T214526Z`.
[group('(6) benchmarks')]
bench-archive run_id:
    mkdir -p benchmarks/history/{{ run_id }}
    cp benchmarks/results/{{ run_id }}/summary.json benchmarks/history/{{ run_id }}/
    cp benchmarks/results/{{ run_id }}/environment.json benchmarks/history/{{ run_id }}/ 2>/dev/null || true
    cp benchmarks/results/{{ run_id }}/levels.jsonl benchmarks/history/{{ run_id }}/ 2>/dev/null || true
    cp benchmarks/results/{{ run_id }}/report.md benchmarks/history/{{ run_id }}/ 2>/dev/null || true
    @echo "archived to benchmarks/history/{{ run_id }} — commit it with the change it validates"

# Open a shell in the benchmark container (debugging).
[group('(6) benchmarks')]
bench-bash:
    just bench-compose '--profile cube --profile bench run --rm --no-deps benchmark bash'

# Stop the benchmark stack.
[group('(6) benchmarks')]
bench-down:
    just bench-compose '--profile cube --profile bench down'

# Print the OpenAPI schema via drf-spectacular.
[group('(3) development')]
openapi:
    @just storage={{ storage }} run python manage.py spectacular --color

# Print the OpenAPI schema using drf-spectacular, using workarounds for more
# reliable client generation.
[group('(3) development')]
openapi-split:
    env SPECTACULAR_SPLIT_REQUEST=true just storage={{ storage }} openapi

