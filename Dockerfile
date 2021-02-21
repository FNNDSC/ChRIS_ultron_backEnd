#
# Docker file for ChRIS production server
#
# Build with
#
#   docker build -t <name> .
#
# For example if building a local version, you could do:
#
#   docker build -t local/chris .
#
# In the case of a proxy (located at say proxy.tch.harvard.edu:3128), do:
#
#    export PROXY="http://proxy.tch.harvard.edu:3128"
#    docker build --build-arg http_proxy=${PROXY} --build-arg UID=$UID -t local/chris .
#
# To run an interactive shell inside this container, do:
#
#   docker run -ti --entrypoint /bin/bash local/chris
#

FROM fnndsc/ubuntu-python3:ubuntu20.04-python3.8.5
MAINTAINER fnndsc "dev@babymri.org"

# Pass a UID on build command line (see above) to set internal UID
ARG UID=1001
ENV UID=$UID DEBIAN_FRONTEND=noninteractive VERSION="0.1"

ENV APPROOT="/home/localuser/chris_backend" REQPATH="/usr/src/requirements"
COPY ["./requirements", "${REQPATH}"]
COPY ["./docker-entrypoint.sh", "/usr/src"]

RUN apt-get update                                               \
  && apt-get install -y locales                                  \
  && export LANGUAGE=en_US.UTF-8                                 \
  && export LANG=en_US.UTF-8                                     \
  && export LC_ALL=en_US.UTF-8                                   \
  && locale-gen en_US.UTF-8                                      \
  && dpkg-reconfigure locales                                    \
  && apt-get install -y libmysqlclient-dev                       \
  && apt-get install -y libssl-dev libcurl4-openssl-dev          \
  && apt-get install -y apache2 apache2-dev                      \
  && apt-get install -y bsdmainutils net-tools inetutils-ping    \
  && pip install -r ${REQPATH}/production.txt                    \
  && useradd -u $UID -ms /bin/bash localuser

# Start as user localuser
USER localuser

# Copy source code and make localuser the owner
COPY --chown=localuser ["./chris_backend", "${APPROOT}"]

WORKDIR $APPROOT
ENTRYPOINT ["/usr/src/docker-entrypoint.sh"]
EXPOSE 8000

# Start ChRIS production server
CMD ["mod_wsgi-express", "start-server", "config/wsgi.py", "--host", "0.0.0.0", "--port", "8000", "--processes", "8", "--server-root", "/home/localuser/mod_wsgi-0.0.0.0:8000"]
#mod_wsgi-express setup-server config/wsgi.py --host 0.0.0.0 --port 8000 --processes 8 --server-name localhost --server-root /home/localuser/mod_wsgi-0.0.0.0:8000
#to start daemon:
#/home/localuser/mod_wsgi-0.0.0.0:8000/apachectl start
#to stop deamon
#/home/localuser/mod_wsgi-0.0.0.0:8000/apachectl stop
