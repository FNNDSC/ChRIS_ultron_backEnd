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

FROM registry.access.redhat.com/ubi9/python-311:1-17.1692772360

COPY --chown=default:root ./requirements/ /tmp/requirements
ARG ENVIRONMENT=production
RUN pip install -r /tmp/requirements/$ENVIRONMENT.txt && rm -rf /tmp/requirements
COPY chris_backend/ ./
RUN env DJANGO_SETTINGS_MODULE=config.settings.common ./manage.py collectstatic

CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "4", "config.wsgi:application"]

LABEL org.opencontainers.image.authors="FNNDSC <dev@babyMRI.org>" \
    org.opencontainers.image.title="ChRIS Backend" \
    org.opencontainers.image.description="ChRIS backend django API server" \
    org.opencontainers.image.url="https://chrisproject.org/" \
    org.opencontainers.image.source="https://github.com/FNNDSC/ChRIS_ultron_backEnd" \
    org.opencontainers.image.documentation="https://github.com/FNNDSC/ChRIS_ultron_backEnd/wiki/" \
    org.opencontainers.image.version="" \
    org.opencontainers.image.licenses="MIT"
