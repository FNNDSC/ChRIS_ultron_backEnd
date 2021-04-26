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

    title -d 1 "Checking required FS directory tree for remote services in host filesystem..."
    mkdir -p FS/remote
    chmod -R 777 FS
    export STOREBASE=$(pwd)/FS/remote
    windowBottom

    title -d 1 "Starting chris_stack production deployment on swarm using " " ./docker-compose.yml"
    declare -a A_CONTAINER=(
    "fnndsc/chris"
    "fnndsc/chris_store"
    "mysql:5"
    "rabbitmq:3"
    "fnndsc/pfcon"
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
    echo "docker stack deploy -c docker-compose.yml chris_stack"
    docker stack deploy -c docker-compose.yml chris_stack
    windowBottom

    title -d 1 "Waiting until chris stack containers are running on swarm"
    for i in {1..30}; do
        sleep 5
            chris=$(docker ps -f name=chris.1. -q)
        if [ -n "$chris" ]; then
          echo "Success: chris container is up"
          break
        fi
    done
    if [ -z "$chris" ]; then
        echo "Error: couldn't start chris container"
        exit 1
    fi
    windowBottom

    title -d 1 "Waiting until CUBE is ready to accept connections..."
    docker exec $chris sh -c 'while ! curl -sSf http://localhost:8000/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    windowBottom

    title -d 1 "Waiting until ChRIS store is ready to accept connections..."
    chris_store=$(docker ps -f name=chris_store.1. -q)
    docker exec $chris_store sh -c 'while ! curl -sSf http://localhost:8010/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    windowBottom

    if [ ! -f FS/.setup ]; then

        title -d 1 "Creating superuser chris in ChRIS store"
        docker exec -it $chris_store sh -c 'python manage.py createsuperuser --username chris --email dev@babymri.org'
        windowBottom

        title -d 1 "Creating superuser chris in CUBE"
        docker exec -it $chris sh -c 'python manage.py createsuperuser --username chris --email dev@babymri.org'
        windowBottom

        title -d 1 "Uploading the plugin fnndsc/pl-dircopy"
        docker exec $chris_store python plugins/services/manager.py add pl-dircopy chris https://github.com/FNNDSC/pl-dircopy fnndsc/pl-dircopy --descriptorstring "$(docker run --rm fnndsc/pl-dircopy dircopy --json 2> /dev/null)"
        windowBottom

        title -d 1 "Uploading the plugin fnndsc/pl-topologicalcopy"
        docker exec $chris_store python plugins/services/manager.py add pl-topologicalcopy chris https://github.com/FNNDSC/pl-topologicalcopy fnndsc/pl-topologicalcopy --descriptorstring "$(docker run --rm fnndsc/pl-topologicalcopy topologicalcopy --json 2> /dev/null)"
        windowBottom

        title -d 1 "Adding host compute environment"
        docker exec $chris python plugins/services/manager.py add host "http://pfcon.remote:5005/api/v1/" --description "Remote compute"
        windowBottom

        title -d 1 "Registering pl-dircopy from store to CUBE"
        docker exec $chris python plugins/services/manager.py register host --pluginname pl-dircopy
        windowBottom

        title -d 1 "Registering pl-topologicalcopy from store to CUBE"
        docker exec $chris python plugins/services/manager.py register host --pluginname pl-topologicalcopy
        windowBottom

        touch FS/.setup
    fi
fi

if [[ "$1" == 'down' ]]; then

    title -d 1 "Destroying chris_stack production deployment on swarm" "from ./docker-compose.yml"
    echo
    docker stack rm chris_stack
    sleep 10
    echo
    printf "Do you want to also remove persistent volumes?"
    read -p  " [y/n] " -n 1 -r
    echo
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] ; then
        sleep 10
        docker volume rm chris_stack_chris_db_data
        docker volume rm chris_stack_chris_store_db_data
        docker volume rm chris_stack_queue_data
        docker volume rm chris_stack_swift_storage
        echo "Removing ./FS tree"
        rm -fr ./FS
    fi
    windowBottom
fi
