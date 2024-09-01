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
attach: (docker-compose '--profile=cube attach chris')

# Open a Python shell.
[group('(3) development')]
shell: (run 'python manage.py shell')

# Open a Bash shell.
[group('(3) development')]
bash: (run 'bash')

# Run chrisomatic, a tool which adds plugins and users to CUBE.
[group('(1) start-up')]
chrisomatic *args: start
    @just docker-compose --profile=cube run --rm chrisomatic chrisomatic {{ args }}

# Run chrisomatic with the contents of chrisomatic/postscript.yml
[group('(1) start-up')]
postscript: (chrisomatic 'postscript.yml')

# Perform database migrations.
[group('(1) start-up')]
migrate: (run 'python manage.py migrate --noinput')

# Run tests, e.g. `just test pacsfiles`
[group('(3) development')]
test *args:
    @just run python manage.py test --force-color {{ args }}

# Run all tests.
[group('(3) development')]
test-all: test-unit test-integration

# Run unit tests.
[group('(3) development')]
test-unit: start-ancillary (run 'python manage.py test --force-color --exclude-tag integration')

# Run integration tests.
[group('(3) development')]
test-integration: start-ancillary (run 'python manage.py test --force-color --tag integration')

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
reap-plugin-instances: (docker-compose 'run --rm pman python -c' '''
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
    @just docker-compose --profile=cube logs {{ args }}

# docker-compose ... run helper function.
[group('(4) docker-compose')]
run +command:
    @just docker-compose --profile=cube run --rm chris {{ command }}

# docker-compose ... helper function.
[group('(4) docker-compose')]
docker-compose +command:
    env UID=$(id -u) GID=$(id -g) DOCKER_SOCK="$(just get-socket)" $(just get-engine) compose {{ command }}

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
