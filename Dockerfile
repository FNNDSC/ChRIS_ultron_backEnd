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

FROM registry.access.redhat.com/ubi9/python-312:1-1765312055

# Pinned deliberately: `:latest` would make the image build irreproducible, which is the
# opposite of the point of adopting a lockfile.
COPY --from=ghcr.io/astral-sh/uv:0.12.11 /uv /uvx /usr/local/bin/

# Install into the s2i-provided venv at /opt/app-root rather than creating .venv, so the
# interpreter and console scripts stay where the rest of the image expects them, and the
# /opt/app-root/src bind mount used in development cannot shadow the environment.
#
# UV_PYTHON_DOWNLOADS=never keeps uv from silently swapping in an interpreter of its own
# if the venv ever stops satisfying requires-python; we want that to fail loudly.
# UV_NO_CACHE=1 keeps uv's download cache out of the image layer.
ENV UV_PROJECT_ENVIRONMENT=/opt/app-root \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1

# Copied before chris_backend/ so that a source-only change does not reinstall
# dependencies. `--locked` fails the build if uv.lock is stale rather than silently
# re-resolving; `--frozen` would skip the check entirely and is the wrong choice here.
ARG ENVIRONMENT=production
COPY --chown=default:root pyproject.toml uv.lock /tmp/build/
RUN cd /tmp/build \
    && if [ "$ENVIRONMENT" = "production" ]; then \
           uv sync --locked --no-dev; \
       else \
           uv sync --locked; \
       fi \
    && rm -rf /tmp/build

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
