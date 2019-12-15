#!/bin/bash

source ./decorate.sh

declare -i STEP=0

title -d 1 "Destroying containerized development environment" "from ./docker-compose_dev.yml]"
echo
printf "Do you want to also remove persistent volumes?"
read -p  " [y/n] " -n 1 -r
echo
echo
if [[ $REPLY =~ ^[Yy]$ ]] ; then
    docker-compose -f docker-compose_dev.yml down -v
    echo "Removing ./FS tree"
    rm -fr ./FS
else
    docker-compose -f docker-compose_dev.yml down
fi
windowBottom

title -d 1 "Stopping swarm cluster..."
    docker swarm leave --force
windowBottom
