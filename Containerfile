FROM registry.access.redhat.com/ubi8/python-38:1-96
LABEL org.opencontainers.image.authors="FNNDSC <dev@babyMRI.org>" \
      org.opencontainers.image.title="ChRIS Ultron Backend" \
      org.opencontainers.image.description="ChRIS backend" \
      org.opencontainers.image.url="https://chrisproject.org/" \
      org.opencontainers.image.source="https://github.com/FNNDSC/ChRIS_ultron_backEnd" \
      org.opencontainers.image.licenses="MIT"
# Pass a UID on build command line (see above) to set internal UID
ARG UID=1001
ARG ENVIRONMENT=production

ENV UID=$UID DEBIAN_FRONTEND=noninteractive VERSION="0.1"
ENV REQPATH="/opt/app-root/src" REQPATH="/opt/app-root/src/requirements"

USER root

WORKDIR /opt/app-root/src

COPY requirements ./requirements
COPY ./podman-entrypoint.sh /opt/app-root/src

RUN yum update -y \
&& pip install --upgrade pip \
&& pip install -r ${REQPATH}/${ENVIRONMENT}.txt

ENTRYPOINT ["/opt/app-root/src/podman-entrypoint.sh"]
EXPOSE 8000

# Start ChRIS production server
CMD ["mod_wsgi-express", "start-server", "config/wsgi.py", "--host", "0.0.0.0", "--port", "8000",  \
"--processes", "4", "--limit-request-body", "5368709120", "--server-root", "/opt/app-root/src/mod_wsgi-0.0.0.0:8000"]
