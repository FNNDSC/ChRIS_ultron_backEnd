compose_file := 'docker-compose_just.yml'

# Start the ChRIS backend in development mode, and attach to the live-reloading server.
dev: chrisomatic attach

# Start the ChRIS backend in development mode.
start: start-ancillary migrate up

# Start services (without running database migrations).
up: (docker-compose '--profile=cube up -d')

# Attach to the chris container.
attach: (docker-compose '--profile=cube attach chris')

# Open a Python shell.
shell: (run 'python manage.py shell')

# Open a Bash shell.
bash: (run 'bash')

# Run chrisomatic, a tool which adds plugins and users to CUBE.
chrisomatic *args: start
    @just docker-compose --profile=cube run --rm chrisomatic chrisomatic {{args}}

# Run chrisomatic with the contents of chrisomatic/postscript.yml
postscript: (chrisomatic 'postscript.yml')

# Perform database migrations.
migrate: (run 'python manage.py migrate --noinput')

# Run tests, e.g. `just test pacsfiles`
test *args:
    @just run python manage.py test --force-color {{args}}

# Run all tests.
test-all: test-unit test-integration

# Run unit tests.
test-unit: (run 'python manage.py test --force-color --exclude-tag integration')

# Run integration tests.
test-integration: start-ancillary (run 'python manage.py test --force-color --tag integration')

# Start dependency services.
start-ancillary: (docker-compose 'up -d')

# Stop services.
down: (docker-compose '--profile=cube --profile=tools down')

# Stop services and remove all data.
nuke: reap-plugin-instances (docker-compose '--profile=cube --profile=tools down -v --remove-orphans')

# Remove all plugin instance containers.
reap-plugin-instances: (
    docker-compose 'run --rm pman python -c' '''
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
    '''
)

# (Re-)build the container image.
build: (docker-compose '--profile=cube build')

# Pull container images.
pull: (docker-compose 'pull')

# Get container logs.
logs *args:
    @just docker-compose --profile=cube logs {{args}}

# docker-compose ... run helper function.
run +command:
    @just docker-compose --profile=cube run --rm chris {{command}}

# docker-compose ... helper function.
docker-compose +command:
    env UID=$(id -u) GID=$(id -g) DOCKER_SOCK=$(just get-socket) $(just get-engine) compose -f '{{ compose_file }}' {{command}}

# Get the container engine to use (docker or podman)
get-engine:
    @if [ -f '.preference' ]; then           \
      cat .preference && exit 0;             \
    elif type podman > /dev/null 2>&1; then  \
      echo podman;                           \
    else                                     \
      echo docker;                           \
    fi                                       \

# Get the docker daemon socket
get-socket:
    @if [ "$(just get-engine)" = 'podman' ]; then     \
      just get-podman-socket;                         \
    else                                              \
      echo '/var/run/docker.sock';                    \
    fi

get-podman-socket: check-podman-socket
    @podman info --format '{{{{ .Host.RemoteSocket.Path }}'

# Ensure that the podman daemon is running.
check-podman-socket:
    @if [ "$(podman info --format '{{{{ .Host.RemoteSocket.Exists }}')" != 'true' ]; then       \
      echo 'Podman daemon not running. Please run `systemctl --user start podman.service`';      \
      exit 1;                                                                                    \
    fi

# Set a preference for using either Docker or Podman.
prefer docker_or_podman:
    @[ '{{docker_or_podman}}' = 'docker' ] || [ '{{docker_or_podman}}' = 'podman' ] \
        || ( \
            >&2 echo 'argument must be either "docker" or "podman"'; \
            exit 1 \
        )
    echo '{{docker_or_podman}}' > .preference

# Remove your preference for Docker or Podman.
unset-preference:
    rm -f .preference
