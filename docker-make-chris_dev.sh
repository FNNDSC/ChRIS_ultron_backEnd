#!/bin/bash
#
# NAME
#
#   docker-make-chris_dev.sh
#
# SYNPOSIS
#
#   docker-make-chris_dev.sh [local|fnndsc[:dev]]
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
#   [local|fnndsc[:dev]] (optional, default = 'fnndsc')
#
#       If specified, denotes the container "family" to use.
#
#       If a colon suffix exists, then this is interpreted to further
#       specify the release.
#
#       The 'fnndsc' family are the containers as hosted on docker hub. 
#       Using 'fnndsc' will always attempt to pull the latest container first.
#
#       The 'local' family are containers that are assumed built on the local
#       machine and assumed to exist. The 'local' containers are used when
#       the 'pfcon/pman/pfioh/pfurl' services are being locally 
#       developed/debugged.
#
#       


source ./decorate.sh 

declare -i STEP=0
declare -i b_restart=0
RESTART=""
HERE=$(pwd)
echo "Starting script in dir $HERE"

CREPO=fnndsc
REL=:dev

while getopts "r:" opt; do
    case $opt in 
        r) b_restart=1
           RESTART=$OPTARG  ;;
    esac
done
shift $(($OPTIND - 1))
if (( $# == 1 )) ; then
    REPO=$1
fi
export CREPO=$(echo $REPO | awk -F \: '{print $1}')
export RELEASE=$(echo $REPO | awk -F \: '{print ":"$2}')

declare -a A_CONTAINER=(
    "chris_dev_backend"
    "pfcon${RELEASE}"
    "pfurl${RELEASE}"
    "pfioh${RELEASE}"
    "pman${RELEASE}"
    "swarm"
    "pfdcm${RELEASE}"
    "pl-pacsquery"
    "pl-pacsretrieve"
)

title -d 1 "Using <$REPO> family containers..."
if [[ $CREPO == "fnndsc" ]] ; then
    echo "Pulling latest version of all containers..."
    for CONTAINER in ${A_CONTAINER[@]} ; do
        echo ""
        CMD="docker pull ${CREPO}/$CONTAINER"
        echo -e "\t\t\t${White}$CMD${NC}"
        echo $sep
        echo $CMD | sh
        echo $sep
    done
fi
windowBottom

if (( b_restart )) ; then
    docker-compose stop ${RESTART}_service && docker-compose rm -f ${RESTART}_service
    docker-compose run --service-ports ${RESTART}_service
else
    title -d 1 "Will use containers with following version info:"
    for CONTAINER in ${A_CONTAINER[@]} ; do
        if [[   $CONTAINER != "chris_dev_backend"   && \
                $CONTAINER != "pl-pacsretrieve"     && \
                $CONTAINER != "pl-pacsquery"        && \
                $CONTAINER != "swarm" ]] ; then
            CMD="docker run ${CREPO}/$CONTAINER --version"
            printf "${White}%40s\t\t" "${CREPO}/$CONTAINER"
            Ver=$(echo $CMD | sh | grep Version)
            echo -e "$Green$Ver"
        fi
    done
    # And for the version of pfurl *inside* pfcon!
    CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/pfcon${RELEASE} --version"
    printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pfcon${RELEASE}"
    Ver=$(echo $CMD | sh | grep Version)
    echo -e "$Green$Ver"
    CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/chris_dev_backend --version"
    printf "${White}%40s\t\t" "pfurl inside ${CREPO}/CUBE"
    Ver=$(echo $CMD | sh | grep Version)
    echo -e "$Green$Ver"
    CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/pl-pacsquery --version"
    printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pl-pacsquery"
    Ver=$(echo $CMD | sh | grep Version)
    echo -e "$Green$Ver"
    CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/pl-pacsretrieve --version"
    printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pl-pacsretrieve"
    Ver=$(echo $CMD | sh | grep Version)
    echo -e "$Green$Ver"
    windowBottom

    title -d 1 "Stopping and restarting the docker swarm... "
    docker swarm leave --force
    docker swarm init
    windowBottom

    title -d 1 "Shutting down any running CUBE and CUBE related containers... "
    docker-compose stop
    docker-compose rm -vf
    for CONTAINER in ${A_CONTAINER[@]} ; do
        printf "%30s" "$CONTAINER"
        docker ps -a                                                        |\
            grep $CONTAINER                                                 |\
            awk '{printf("docker stop %s && docker rm -vf %s\n", $1, $1);}' |\
            sh >/dev/null
        printf "${Green}%20s${NC}\n" "done"
    done
    windowBottom

    cd $HERE
    title -d 1 "Changing permissions to 755 on" " $(pwd)"
    echo "chmod -R 755 $(pwd)"
    chmod -R 755 $(pwd)
    windowBottom

    title -d 1 "Creating tmp dirs for volume mounting into containers..."
    echo "${STEP}.1: Remove tree root 'FS'.."
    rm -fr ./FS 
    echo "${STEP}.2: Create tree structure for remote services in host filesystem..."
    mkdir -p FS/local
    chmod 777 FS/local
    mkdir -p FS/remote
    chmod 777 FS/remote
    chmod 777 FS
    cd FS/remote
    echo -e "${STEP}.3 For pman override to swarm containers, exporting\n\tSTOREBASE=$(pwd)... "
    export STOREBASE=$(pwd)
    cd $HERE
    windowBottom

    title -d 1 "Starting CUBE containerized development environment using " " ./docker-compose.yml"
    # export HOST_IP=$(ip route | grep -v docker | awk '{if(NF==11) print $9}')
    # echo "Exporting HOST_IP=$HOST_IP as environment var..."
    echo "docker-compose up -d"
    docker-compose up -d
    windowBottom

    title -d 1 "Waiting until mysql server is ready to accept connections..."
    docker-compose exec chris_dev_db sh -c 'while ! mysqladmin -uroot -prootp status 2> /dev/null; do sleep 5; done;'
    # Give all permissions to chris user in the DB. This is required for the Django tests:
    docker-compose exec chris_dev_db mysql -uroot -prootp -e 'GRANT ALL PRIVILEGES ON *.* TO "chris"@"%"'
    windowBottom

    title -d 1 "Making migrations..."
    docker-compose exec chris_dev python manage.py migrate
    windowBottom

    title -d 1 "Registering plugins..."
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
                        "local/pl-geretrieve"
                        "local/pl-gepush"
                        )
    declare -i i=1
    declare -i STEP=10
    for plugin in "${plugins[@]}"; do 
        echo "${STEP}.$i: Registering $plugin..."
        python3 plugins/services/manager.py --add ${plugin} 2> /dev/null; 
        ((i++))
    done'
    windowBottom

    title -d 1 "Running Django tests..."
    docker-compose exec chris_dev python manage.py test
    windowBottom

    title -d 1 "Restarting Django development server..."
    docker-compose restart chris_dev
    windowBottom

    title -d 1 "ChRIS API user creation"
    echo 'Now create two users. Please name one of the users "chris"'
    echo ""
    docker-compose exec chris_dev python manage.py createsuperuser
    docker-compose exec chris_dev python manage.py createsuperuser
    windowBottom

    title -d 1 "Restarting Django development server in interactive mode..."
    docker-compose stop chris_dev
    docker-compose rm -f chris_dev
    docker-compose run --service-ports chris_dev
    echo ""
    windowBottom
fi
