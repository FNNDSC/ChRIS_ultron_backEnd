#!/bin/bash
#
# NAME
#
#   deploy.sh
#
# SYNPOSIS
#
#   deploy.sh                   [-h]
#                               [-O <swarm|kubernetes>] \
#                               [-S <storeBase>]        \
#                               [up|down]
#
# DESC
#
#   'deploy.sh' script will depending on the argument deploy the ChRIS set
#    of services in production or tear down the system.
#
# TYPICAL CASES:
#
#   Deploy ChRIS services into a Swarm cluster:
#
#       deploy.sh up
#
#
#   Deploy ChRIS services into a Kubernetes cluster:
#
#       deploy.sh -O kubernetes up
#
# ARGS
#
#
#   -h
#
#       Optional print usage help.
#
#   -O <swarm|kubernetes>
#
#       Explicitly set the orchestrator. Default is swarm.
#
#   -S <storeBase>
#
#       Explicitly set the STOREBASE dir to <storeBase>. This is the remote ChRIS
#       filesystem where pfcon and plugins share data (usually externally mounted NFS).
#
#   [up|down] (optional, default = 'up')
#
#       Denotes whether to fire up or tear down the production set of services.
#
#


source ./decorate.sh
source ./cparse.sh

declare -i STEP=0
ORCHESTRATOR=swarm
HERE=$(pwd)

print_usage () {
    echo "Usage: ./deploy.sh [-h] [-O <swarm|kubernetes>] [-S <storeBase>] [up|down]"
    exit 1
}

while getopts ":hO:S:" opt; do
    case $opt in
        h) print_usage
           ;;
        O) ORCHESTRATOR=$OPTARG
           if ! [[ "$ORCHESTRATOR" =~ ^(swarm|kubernetes)$ ]]; then
              echo "Invalid value for option -- O"
              print_usage
           fi
           ;;
        S) STOREBASE=$OPTARG
           ;;
        \?) echo "Invalid option -- $OPTARG"
            print_usage
            ;;
        :) echo "Option requires an argument -- $OPTARG"
           print_usage
           ;;
    esac
done
shift $(($OPTIND - 1))

COMMAND=up
if (( $# == 1 )) ; then
    COMMAND=$1
    if ! [[ "$COMMAND" =~ ^(up|down)$ ]]; then
        echo "Invalid value $COMMAND"
        print_usage
    fi
fi

title -d 1 "Setting global exports..."
    if [ -z ${STOREBASE+x} ]; then
        if [[ ! -d CHRIS_REMOTE_FS ]] ; then
            mkdir CHRIS_REMOTE_FS
        fi
        STOREBASE=$HERE/CHRIS_REMOTE_FS
    else
        if [[ ! -d $STOREBASE ]] ; then
            mkdir -p $STOREBASE
        fi
    fi
    echo -e "exporting STOREBASE=$STOREBASE "                      | ./boxes.sh
    export STOREBASE=$STOREBASE
windowBottom

if [[ "$COMMAND" == 'up' ]]; then

    title -d 1 "Starting ChRIS production deployment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack deploy -c swarm/prod_deployments/docker-compose.yml chris_stack"  | ./boxes.sh ${LightCyan}
        docker stack deploy -c swarm/prod_deployments/docker-compose.yml chris_stack
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        echo "coming up soon..."
        exit 0
    fi
    windowBottom

    title -d 1 "Waiting for ChRIS containers to start running on $ORCHESTRATOR"
    echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
    for i in {1..50}; do
        sleep 5
        if [[ $ORCHESTRATOR == swarm ]]; then
            chris=$(docker ps -f name=chris.1. -q)
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            chris=$(kubectl get pods --selector="app=chris,env=production" --field-selector=status.phase=Running --output=jsonpath='{.items[*].metadata.name}')
        fi
        if [ -n "$chris" ]; then
          echo "Success: chris container is running on $ORCHESTRATOR"      | ./boxes.sh ${Green}
          break
        fi
    done
    if [ -z "$chris" ]; then
        echo "Error: couldn't start chris container on $ORCHESTRATOR"      | ./boxes.sh ${Red}
        exit 1
    fi
    windowBottom

    title -d 1 "Waiting until CUBE is ready to accept connections..."
    docker exec $chris sh -c 'while ! curl -sSf http://localhost:8000/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    windowBottom

    title -d 1 "Waiting until ChRIS store is ready to accept connections..."
    if [[ $ORCHESTRATOR == swarm ]]; then
        chris_store=$(docker ps -f name=chris_store.1. -q)
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        chris_store=$(kubectl get pods --selector="app=chris-store,env=production" --output=jsonpath='{.items[*].metadata.name}')
    fi
    docker exec $chris_store sh -c 'while ! curl -sSf http://localhost:8010/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    windowBottom

    if [ ! -f $STOREBASE/.setup ]; then

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

        touch $STOREBASE/.setup
    fi
fi

if [[ "$COMMAND" == 'down' ]]; then

    title -d 1 "Destroying ChRIS production deployment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack rm chris_stack"                               | ./boxes.sh ${LightCyan}
        docker stack rm chris_stack
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        echo " coming up soon..."       | ./boxes.sh ${LightCyan}
    fi
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
        echo "Removing STOREBASE tree $STOREBASE"                       | ./boxes.sh
        rm -fr $STOREBASE
    fi
    windowBottom
fi
