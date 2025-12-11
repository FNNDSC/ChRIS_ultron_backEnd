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
#    --build-arg http_proxy=${PROXY}
#
# For example if building a local development image:
#
# docker build --build-arg http_proxy=${PROXY} --build-arg ENVIRONMENT=local -t local/chris:dev .
#

FROM registry.access.redhat.com/ubi9/python-312:1-1765312055

COPY --chown=default:root ./requirements/ /tmp/requirements
ARG ENVIRONMENT=production
RUN pip install -r /tmp/requirements/$ENVIRONMENT.txt && rm -rf /tmp/requirements
COPY chris_backend/ ./
RUN if [ "$ENVIRONMENT" = "production" ]; then \
    env DJANGO_SETTINGS_MODULE=config.settings.common ./manage.py collectstatic; fi

CMD ["python3", "-m", "uvicorn", "--host", "0.0.0.0", "--port", "8000", "config.asgi:application"]
