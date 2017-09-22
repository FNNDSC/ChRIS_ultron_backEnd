#!/bin/bash
#
# NAME
#
#   docker-make-chris_dev.sh
#
# SYNPOSIS
#
#   docker-make-chris_dev.sh [local|fnndsc]
#
# DESC
# 
#   'dockeer-make-chris_dev.sh' is the main entry point for instantiating a 
#   complete backend dev environment.
#
#   It creates a pattern of directories and symbolic links that reflect the
#   declarative environment of the docker-compose.yml contents.
#
# ARGS
#
#   [local|fnndsc] (optional, default = 'fnndsc')
#
#       If specified, denotes the container "family" to use. 
#
#       The 'fnndsc' family are the containers as hosted on docker hub. 
#       Using 'fnndsc' will always attempt to pull the latest container first.
#
#       The 'local' family are containers that are assumed built on the local
#       machine and assumed to exist. The 'local' containers are used when
#       the 'pfcon/pman/pfioh/pfurl' services are being locally 
#       developed/debugged.
#

HERE=$(pwd)
echo "Starting script in dir $HERE"
sep="_______________________________________________________________________________"

CREPO=fnndsc
if (( $# == 1 )) ; then
    CREPO=$1
fi
export CREPO=$CREPO

declare -a A_CONTAINER=(
    "chris_dev_backend"
    "pfcon"
    "pfurl"
    "pfioh"
    "pman"
)
echo "Using containers from <$CREPO>."
if [[ $CREPO == "fnndsc" ]] ; then
    echo "Pulling latest version of all containers..."
    for CONTAINER in ${A_CONTAINER[@]} ; do
        echo ""
        CMD="docker pull ${CREPO}/$CONTAINER"
        echo -e "\t\t\t$CMD"
        echo $sep
        echo $CMD | sh
        echo $sep
    done
fi
echo "$sep"
echo "Will use containers with following version info:"
for CONTAINER in ${A_CONTAINER[@]} ; do
    if [[ $CONTAINER != "chris_dev_backend" ]] ; then
        CMD="docker run ${CREPO}/$CONTAINER --version"
        printf "%30s\t\t" "${CREPO}/$CONTAINER"
        echo $CMD | sh | grep Version
    fi
done
# And for the version of pfurl *inside* pfcon!
CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/pfcon --version"
printf "%30s\t\t" "pfurl inside ${CREPO}/pfcon"
echo $CMD | sh | grep Version

echo "$sep"
echo "Shutting down any running CUBE and CUBE related containers.."
docker-compose stop
docker-compose rm -vf
for CONTAINER in ${A_CONTAINER[@]} ; do
    printf "%30s" "$CONTAINER"
    docker ps -a                                                        |\
        grep $CONTAINER                                                 |\
        awk '{printf("docker stop %s && docker rm -vf %s\n", $1, $1);}' |\
        sh >/dev/null
    printf "%20s\n" "down"
done

rm -fr ./FS 2>/dev/null
echo "$sep"
cd $HERE
echo "0.0: Changing permissions to 755 for $(pwd)..."
chmod -R 755 $(pwd)

echo ""
echo "$sep"
echo "1.0: Creating tmp dirs for volume mounting into containers..."
echo "1.1: Remove tree root 'FS'.."
rm -fr ./FS 2>/dev/null
echo "1.2: Create tree structure for remote services in host filesystem..."
# mkdir -p FS/local
mkdir -p FS/remote
# mkdir -p FS/users
# chmod 777 FS/local
chmod 777 FS/remote
# chmod 777 FS/users
# echo "1.3: Create tree structure to emulate volume mapping"
# echo "1.3: This allows for easy switching/running between"
# echo "1.3: containerized and non-containerized environments."
# sudo rm -fr /hostFS 2>/dev/null
# sudo mkdir -p /hostFS
# cd /hostFS
# sudo ln -s ${HERE}/FS/local   pfconFS
# sudo ln -s ${HERE}/FS/remote  storeBase
cd $HERE

echo "$sep"
echo "2.0: Starting CUBE containerized development environment from ./docker-compose.yml..."
# export HOST_IP=$(ip route | grep -v docker | awk '{if(NF==11) print $9}')
# echo "Exporting HOST_IP=$HOST_IP as environment var..."
docker-compose up -d

echo "$sep"
echo "3.0: Waiting until mysql server is ready to accept connections..."
docker-compose exec chris_dev_db sh -c 'while ! mysqladmin -uroot -prootp status 2> /dev/null; do sleep 5; done;'
# Give all permissions to chris user in the DB. This is required for the Django tests:
docker-compose exec chris_dev_db mysql -uroot -prootp -e 'GRANT ALL PRIVILEGES ON *.* TO "chris"@"%"'

echo "$sep"
echo "4.0: Making migrations..."
docker-compose exec chris_dev python manage.py migrate

echo "$sep"
echo "5.0: Registering plugins..."
# Declare an array variable for the list of plugin dock images
# Add a new plugin image name to the list if you want it to be automatically registered
docker-compose exec chris_dev /bin/bash -c \
  'declare -a plugins=("fnndsc/pl-simplefsapp"
                       "fnndsc/pl-simpledsapp"
                       "fnndsc/pl-pacsquery"
                       "fnndsc/pl-pacsretrieve"
                       "fnndsc/pl-med2img"
                       "fnndsc/pl-s3retrieve"
                       "fnndsc/pl-s3push"
                       "fnndsc/pl-dircopy"
                      )
  declare -i i=1
  for plugin in "${plugins[@]}"; do 
      echo "5.1.$i: Registering $plugin..."
      python3 plugins/services/manager.py --add ${plugin} 2> /dev/null; 
      ((i++))
  done'

echo "$sep"
echo "6.0: Running Django tests..."
docker-compose exec chris_dev python manage.py test

echo "$sep"
echo "7.0: Restarting Django development server..."
docker-compose restart chris_dev

echo "$sep"
echo "8.0: Now create two ChRIS API users..."
echo 'Please name one of the users "chris"'
echo ""
docker-compose exec chris_dev python manage.py createsuperuser
docker-compose exec chris_dev python manage.py createsuperuser

echo "$sep"
echo "9.0: Restarting Django development server in interactive mode..."
docker-compose stop chris_dev
docker-compose rm -f chris_dev
docker-compose run --service-ports chris_dev
echo ""

