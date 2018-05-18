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
    a_VOLS=(
        "chris_dev_db_data"
        "chris_store_dev_db_data"
        "swift_storage"
    )
    a_PVOLS=()
    for vol in ${a_VOLS[@]}; do
        SCANTXT=$(printf "Scanning for '%s'... " "$vol")
        printf "%50s" "$SCANTXT"
        DOCKERVOLNAME=$(docker volume ls | grep -v DRIVER | awk {'print $2'} | grep $vol)
        if (( ${#DOCKERVOLNAME} )); then
            printf "${Green}[ %s ]${NC}\n" "$DOCKERVOLNAME"
        else
            printf "${Red}[ Not found. ]${NC}\n"
        fi
        a_PVOLS+=($DOCKERVOLNAME)
    done
    printf "\n"
    for VOL in ${a_PVOLS[@]} ; do 
        printf "${Cyan}Do you want to remove persistent volume ${Green}[ $VOL ]${Cyan}?${NC}"
        read -p  " [y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] ; then
            docker volume rm $VOL
        fi
    done
windowBottom