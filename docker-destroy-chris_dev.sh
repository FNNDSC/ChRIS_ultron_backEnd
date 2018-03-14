#!/bin/bash

source ./decorate.sh

title -d 1 "Destroying ChRIS containerized development environment" "from ./docker-compose.yml"
windowBottom

title -d 1 "Stopping services..."
    docker-compose stop
windowBottom

title -d 1 "Removing all containers..."
    docker-compose rm -vf 
windowBottom

title -d 1 "Stopping the swarm..."
    docker swarm leave --force
windowBottom

title -d 1 "Destroying persistent volumes..."
    basedir=`pwd | xargs basename | awk '{print tolower($0)}'`
    a_PVOLS=(
        "${basedir//_}_chris_dev_db_data"
        "${basedir//_}_chris_store_dev_db_data"
        "${basedir//_}_swift_storage"
    )
    for VOL in ${a_PVOLS[@]} ; do 
        read -p  "Do you want to remove persistent volume $VOL? " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] ; then
            docker volume rm $VOL
        fi
    done
windowBottom