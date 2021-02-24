#!/bin/bash

G_SYNOPSIS="

 NAME

	docker-deploy.sh

 SYNOPSIS

	docker-deploy.sh [up|down]

 ARGS

	[up|down]
	Denotes whether to fire up or tear down the production set of services.

 DESCRIPTION

	docker-deploy.sh script will depending on the argument deploy the Chris set
    of services in production or tear down the system.

"

if [[ "$#" -eq 0 ]] || [[ "$#" -gt 1 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi

source ./decorate.sh

declare -i STEP=0


if [[ "$1" == 'up' ]]; then

    title -d 1 "Stopping and restarting docker swarm cluster... "
    docker swarm leave --force
    docker swarm init --advertise-addr 127.0.0.1
    windowBottom

    title -d 1 "Checking required FS directory tree for remote services in host filesystem..."
    mkdir -p FS/remote
    chmod -R 777 FS
    export STOREBASE=$(pwd)/FS/remote
    windowBottom

    title -d 1 "Starting containerized production environment using " " ./docker-compose.yml"
    declare -a A_CONTAINER=(
    "fnndsc/chris"
    "fnndsc/chris_store"
    "mysql:5"
    "rabbitmq:3"
    "fnndsc/pfcon"
    "fnndsc/pfioh"
    "fnndsc/pman"
    "fnndsc/docker-swift-onlyone"
    )
    echo "Pulling latest version of all service containers..."
    for CONTAINER in ${A_CONTAINER[@]} ; do
        echo ""
        CMD="docker pull $CONTAINER"
        echo -e "\t\t\t${White}$CMD${NC}"
        echo $sep
        echo $CMD | sh
        echo $sep
    done
    echo "docker-compose up -d"
    docker-compose up -d
    windowBottom

    title -d 1 "Waiting until ChRIS store is ready to accept connections..."
    docker-compose exec chris_store sh -c 'while ! curl -sSf http://localhost:8010/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    windowBottom

    title -d 1 "Waiting until CUBE is ready to accept connections..."
    docker-compose exec chris sh -c 'while ! curl -sSf http://localhost:8000/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    windowBottom

    if [ ! -f FS/.setup ]; then

        title -d 1 "Creating superuser chris in ChRIS store"
        docker-compose exec chris_store sh -c 'python manage.py createsuperuser --username chris --email dev@babymri.org'
        windowBottom

        title -d 1 "Creating superuser chris in CUBE"
        docker-compose exec chris sh -c 'python manage.py createsuperuser --username chris --email dev@babymri.org'
        windowBottom

        title -d 1 "Uploading the plugin fnndsc/pl-dircopy"
        docker-compose exec chris_store python plugins/services/manager.py add pl-dircopy chris https://github.com/FNNDSC/pl-dircopy fnndsc/pl-dircopy --descriptorstring "$(docker run --rm fnndsc/pl-dircopy dircopy --json 2> /dev/null)"
        windowBottom

        title -d 1 "Uploading the plugin fnndsc/pl-topologicalcopy"
        docker-compose exec chris_store python plugins/services/manager.py add pl-topologicalcopy chris https://github.com/FNNDSC/pl-topologicalcopy fnndsc/pl-topologicalcopy --descriptorstring "$(docker run --rm fnndsc/pl-topologicalcopy topologicalcopy --json 2> /dev/null)"
        windowBottom

        title -d 1 "Adding host compute environment"
        docker-compose exec chris python plugins/services/manager.py add host "http://pfcon.local:5005/api/v1/" --description "Local compute"
        windowBottom

        title -d 1 "Registering pl-dircopy from store to CUBE"
        docker-compose exec chris python plugins/services/manager.py register host --pluginname pl-dircopy
        windowBottom

        title -d 1 "Registering pl-topologicalcopy from store to CUBE"
        docker-compose exec chris python plugins/services/manager.py register host --pluginname pl-topologicalcopy
        windowBottom

        touch FS/.setup
    fi
fi

if [[ "$1" == 'down' ]]; then

    export STOREBASE=${STOREBASE}

    title -d 1 "Destroying containerized production environment" "from ./docker-compose.yml"
    echo
    printf "Do you want to also remove persistent volumes?"
    read -p  " [y/n] " -n 1 -r
    echo
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] ; then
        docker-compose down -v
        echo "Removing ./FS tree"
        rm -fr ./FS
    else
        docker-compose down
    fi
    windowBottom

    title -d 1 "Stopping swarm cluster..."
    docker swarm leave --force
    windowBottom
fi
