#
# Docker file for CUBE image
#
# Build production image:
#
#   docker build -t <name> .
#
# For example if building a local production image:
#
#   docker build -t local/chris .
#
# Build development image:
#
#   docker build --build-arg ENVIRONMENT=local -t <name>:<tag> .
#
# For example if building a local development image:
#
#   docker build --build-arg ENVIRONMENT=local -t local/chris:dev .
#
# In the case of a proxy (located at say proxy.tch.harvard.edu:3128), do:
#
#    export PROXY="http://proxy.tch.harvard.edu:3128"
#
# then add to any of the previous build commands:
#
#    --build-arg https_proxy=${PROXY} --build-arg http_proxy=${PROXY}
#
# For example if building a local development image:
#
# docker build --build-arg https_proxy=${PROXY} --build-arg http_proxy=${PROXY} --build-arg ENVIRONMENT=local -t local/chris:dev .
#
# https_proxy (PyPI is HTTPS) and http_proxy are predefined build args, so they need
# no ARG declaration to reach RUN. 
# Note that the FROM and COPY --from image pulls do not use build args at all -- those go 
# through the container engine's own proxy configuration.
#

# The `1-<timestamp>` tags are individual, immutable builds of the same stream, so this
# pins the OS layer as firmly as the digest does for the benchmark image, and stays
# readable. Bump it deliberately for OS security updates.
FROM registry.access.redhat.com/ubi9/python-312:1-1789044838

# Pinned deliberately: `:latest` would make the image build irreproducible, which is the
# opposite of the point of adopting a lockfile.
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /usr/local/bin/

# Install into the s2i-provided venv at /opt/app-root rather than creating .venv, so the
# interpreter and console scripts stay where the rest of the image expects them, and the
# /opt/app-root/src bind mount used in development cannot shadow the environment.
#
# UV_PYTHON_DOWNLOADS=never keeps uv from silently swapping in an interpreter of its own
# if the venv ever stops satisfying requires-python; we want that to fail loudly.
# UV_LINK_MODE=copy because uv's cache (a cache mount below) and the venv are on
# different filesystems, where uv cannot hardlink.
ENV UV_PROJECT_ENVIRONMENT=/opt/app-root \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# pyproject.toml and uv.lock are bind-mounted into the working directory, so they never
# land in a layer. The builder still has to key this step on their content, which Podman
# does only from 5.4: see `just check-builder`.
#
# uv's cache is a cache mount, kept by the builder between builds and never written to a
# layer, so a rebuild after a lock change only downloads (or, for python-ldap, compiles)
# what changed. uid/gid are the image's default user, which runs uv. It lives under /tmp
# rather than uv's default under $HOME because Podman 5.4 (not 5.7) leaves the parent
# directories it creates for a mount target in the image, owned by root: a root-owned
# $HOME/.cache otherwise.
#
#`--locked` fails the build if uv.lock is stale rather than silently re-resolving;
#`--frozen` would skip the check entirely and is the wrong choice here.
ARG ENVIRONMENT=production
RUN --mount=type=cache,target=/tmp/uv-cache,uid=1001,gid=0 \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    export UV_CACHE_DIR=/tmp/uv-cache \
    && if [ "$ENVIRONMENT" = "production" ]; then \
           uv sync --locked --no-dev; \
       else \
           uv sync --locked; \
       fi

COPY chris_backend/ ./

# Development images skip collectstatic but whitenoise's middleware warns once per
# instantiation when STATIC_ROOT is missing. An empty directory is the honest state:
# under DEBUG, runserver serves static files from the app directories instead.
# The path is read back from settings so it cannot drift from common.py.
RUN if [ "$ENVIRONMENT" = "production" ]; then \
        env DJANGO_SETTINGS_MODULE=config.settings.common ./manage.py collectstatic; \
    else \
        mkdir -p "$(env DJANGO_SETTINGS_MODULE=config.settings.common \
            python3 -c 'from django.conf import settings; print(settings.STATIC_ROOT)')"; \
    fi

CMD ["python3", "-m", "uvicorn", "--host", "0.0.0.0", "--port", "8000", "config.asgi:application"]
