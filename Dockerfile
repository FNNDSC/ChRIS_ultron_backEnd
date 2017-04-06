# Docker file for ChRIS development server

FROM fnndsc/ubuntu-python3:latest
MAINTAINER fnndsc "dev@babymri.org"

ENV APPROOT="/usr/src/chris_backend" REQPATH="/usr/src/requirements" VERSION="0.1"
COPY ["./requirements", "${REQPATH}"]
COPY ["./docker-entrypoint.sh", "/usr/src"]

RUN apt-get update \
  && apt-get install -y libmysqlclient-dev dcmtk imagemagick\
  && apt-get install -y libssl-dev libcurl4-openssl-dev \
  && apt-get install -y apache2 apache2-dev \
  && pip3 install -r ${REQPATH}/local.txt

WORKDIR $APPROOT
ENTRYPOINT ["/usr/src/docker-entrypoint.sh"]
EXPOSE 8000 5010
#CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]
