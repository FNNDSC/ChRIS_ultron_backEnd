# Docker file for ChRIS development environment

FROM ubuntu:latest
MAINTAINER fnndsc "dev@babymri.org"

ENV APPROOT="/usr/src/chris_backend" REQPATH="/usr/src/requirements" VERSION="0.1"
COPY ["./requirements", "${REQPATH}"]

RUN apt-get update \
  && apt-get install -y python3-pip python3-dev libmysqlclient-dev \
  && apt-get install -y libssl-dev libcurl4-openssl-dev \
  && apt-get install -y apache2 apache2-dev \
  && echo "alias python=python3" > ~/.bashrc \
  && echo "alias pip=pip3" >> ~/.bashrc \
  && pip3 install -r ${REQPATH}/local.txt

WORKDIR $APPROOT
ENTRYPOINT ["python3", "manage.py"]
EXPOSE 8000
CMD ["runserver", "0.0.0.0:8000"]
