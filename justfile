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

# docker-compose ... run helper function.
run +command:
    @just docker-compose --profile=cube run --rm chris {{command}}

# docker-compose ... helper function.
docker-compose +command:
    env UID=$(id -u) GID=$(id -g) docker compose -f '{{ compose_file }}' {{command}}
