#
# Docker file for ChRIS development server
#
# Build with
#
#   docker build -t <name> .
#
# For example if building a local version, you could do:
#
#   docker build -t local/chris_dev_backend .
#
# In the case of a proxy (located at 192.168.13.14:3128), do:
#
#    docker build --build-arg http_proxy=http://192.168.13.14:3128 --build-arg UID=$UID -t local/chris_dev_backend .
#
# To run an interactive shell inside this container, do:
#
#   docker run -ti --entrypoint /bin/bash local/chris_dev_backend
#
# To pass an env var HOST_IP to container, do:
#
#   docker run -ti -e HOST_IP=$(ip route | grep -v docker | awk '{if(NF==11) print $9}') --entrypoint /bin/bash local/chris_dev_backend
#

FROM fnndsc/ubuntu-python3:latest
MAINTAINER fnndsc "dev@babymri.org"

ENV APPROOT="/usr/src/chris_backend" REQPATH="/usr/src/requirements" VERSION="0.1"
COPY ["./requirements", "${REQPATH}"]
COPY ["./docker-entrypoint.sh", "/usr/src"]

# Pass a UID on build command line (see above) to set internal UID
ARG UID=1001
ENV UID=$UID

RUN apt-get update \
  && apt-get install sudo                                             \
  && useradd -u $UID -ms /bin/bash localuser                          \
  && addgroup localuser sudo                                          \
  && echo "localuser:localuser" | chpasswd                            \
  && adduser localuser sudo                                           \
  && apt-get install -y libmysqlclient-dev                            \
  && apt-get install -y libssl-dev libcurl4-openssl-dev               \
  && apt-get install -y apache2 apache2-dev bsdmainutils vim net-tools inetutils-ping \
  && pip install --upgrade pip                                        \
  && pip3 install -r ${REQPATH}/local.txt                             \
  && chmod 777 /usr/src                                               \
  # && chmod 777 /usr/src/docker-entrypoint.py                          \
  && mkdir /usr/users                                                 \
  && chmod 777 /usr/users                                             \
  && echo "localuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# RUN chmod 777 /usr/users

WORKDIR $APPROOT
ENTRYPOINT ["/usr/src/docker-entrypoint.sh"]
EXPOSE 8000 5005

# Start as user $UID
# For now this is disabled so the service runs as root to 
# easily write to the managed db volume.
# USER $UID

# CMD ["manage.py", "runserver", "0.0.0.0:8000"]
