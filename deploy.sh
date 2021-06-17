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
#                               [-N <namespace>]        \
#                               [-T <host|nfs>]         \
#                               [-P <nfsServerIp>]      \
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
#   Deploy ChRIS services into a single-machine Swarm cluster:
#
#       deploy.sh up
#
#
#   Deploy ChRIS services into a single-machine Kubernetes cluster:
#
#       deploy.sh -O kubernetes up
#
#
#   Deploy ChRIS services into a multi-machine Kubernetes cluster:
#
#       deploy.sh -O kubernetes -T nfs -S <storeBase> -P <nfsServerIp> up
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
#   -N <namespace>
#
#       Explicitly set the kubernetes namespace to <namespace>. Default is chris.
#       Not used for swarm.
#
#   -T <host|nfs>
#
#       Explicitly set the storage type for the STOREBASE dir. Default is host.
#       Note: The nfs storage type is not implemented for swarm orchestrator yet.
#
#   -P <nfsServerIp>
#
#       Set the IP address of the NFS server. Required when storage type is set to 'nfs'.
#       Not used for 'host' storage type.
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
NAMESPACE=chris
STORAGE_TYPE=host
HERE=$(pwd)

print_usage () {
    echo "Usage: ./deploy.sh [-h] [-O <swarm|kubernetes>] [-N <namespace>] [-T <host|nfs>]
         [-P <nfsServerIp>] [-S <storeBase>] [up|down]"
    exit 1
}

while getopts ":hO:N:T:P:S:" opt; do
    case $opt in
        h) print_usage
           ;;
        O) ORCHESTRATOR=$OPTARG
           if ! [[ "$ORCHESTRATOR" =~ ^(swarm|kubernetes)$ ]]; then
              echo "Invalid value for option -- O"
              print_usage
           fi
           ;;
        N) NAMESPACE=$OPTARG
           ;;
        T) STORAGE_TYPE=$OPTARG
           if ! [[ "$STORAGE_TYPE" =~ ^(host|nfs)$ ]]; then
              echo "Invalid value for option -- T"
              print_usage
           fi
           ;;
        P) NFS_SERVER=$OPTARG
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

if [[ $STORAGE_TYPE == nfs ]]; then
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo -e "Sorry, nfs storage type is not supported for swarm orchestrator yet"  | ./boxes.sh
        exit 1
    fi
    if [ -z ${NFS_SERVER+x} ]; then
        echo "-P <NFS_SERVER> (the NFS server ip address) must be specified or the shell
             environment variable NFS_SERVER must be set when using nfs storage type"
        print_usage
    fi
    if [ -z ${STOREBASE+x} ]; then
        echo "-S <storeBase> must be specified or the shell environment variable STOREBASE
             must be set when using nfs storage type"
        print_usage
    fi
fi

COMMAND=up
if (( $# == 1 )) ; then
    COMMAND=$1
    if ! [[ "$COMMAND" =~ ^(up|down)$ ]]; then
        echo "Invalid value $COMMAND"
        print_usage
    fi
fi

title -d 1 "Setting global exports..."
    if [[ $STORAGE_TYPE == host ]]; then
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
    fi
    echo -e "ORCHESTRATOR=$ORCHESTRATOR"                          | ./boxes.sh
    echo -e "exporting STORAGE_TYPE=$STORAGE_TYPE"                | ./boxes.sh
    export STORAGE_TYPE=$STORAGE_TYPE
    if [[ $STORAGE_TYPE == nfs ]]; then
        echo -e "exporting NFS_SERVER=$NFS_SERVER"                | ./boxes.sh
        export NFS_SERVER=$NFS_SERVER
    fi
    echo -e "exporting STOREBASE=$STOREBASE"                      | ./boxes.sh
    export STOREBASE=$STOREBASE
    if [[ $ORCHESTRATOR == kubernetes ]]; then
        echo -e "exporting NAMESPACE=$NAMESPACE"                  | ./boxes.sh
        export NAMESPACE=$NAMESPACE
    fi
windowBottom

if [[ "$COMMAND" == 'up' ]]; then

    title -d 1 "Starting ChRIS production deployment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack deploy -c swarm/prod/docker-compose.yml chris_stack"  | ./boxes.sh ${LightCyan}
        docker stack deploy -c swarm/prod/docker-compose.yml chris_stack
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        echo "kubectl create namespace $NAMESPACE"   | ./boxes.sh ${LightCyan}
        namespace=$(kubectl get namespaces $NAMESPACE --no-headers -o custom-columns=:metadata.name 2> /dev/null)
        if [ -z "$namespace" ]; then
            kubectl create namespace $NAMESPACE
        else
            echo "$NAMESPACE namespace already exists, skipping creation"
        fi
        if [[ $STORAGE_TYPE == host ]]; then
            echo "kubectl kustomize kubernetes/prod/overlays/host | envsubst | kubectl apply -f -"  | ./boxes.sh ${LightCyan}
            kubectl kustomize kubernetes/prod/overlays/host | envsubst | kubectl apply -f -
        else
            echo "kubectl kustomize kubernetes/prod/overlays/nfs | envsubst | kubectl apply -f -"  | ./boxes.sh ${LightCyan}
            kubectl kustomize kubernetes/prod/overlays/nfs | envsubst | kubectl apply -f -
        fi
    fi
    windowBottom

    title -d 1 "Waiting for ChRIS containers to start running on $ORCHESTRATOR"
    echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
    for i in {1..50}; do
        sleep 5
        if [[ $ORCHESTRATOR == swarm ]]; then
            chris=$(docker ps -f name=chris.1. -q)
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            chris=$(kubectl get pods --namespace $NAMESPACE --selector="app=chris,env=production" --field-selector=status.phase=Running --output=jsonpath='{.items[*].metadata.name}')
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
    if [[ $ORCHESTRATOR == swarm ]]; then
        docker exec $chris sh -c 'while ! curl -sSf http://localhost:8000/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        kubectl exec $chris --namespace $NAMESPACE -- sh -c 'while ! curl -sSf http://localhost:8000/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    fi
    windowBottom

    title -d 1 "Waiting until ChRIS store is ready to accept connections..."
    if [[ $ORCHESTRATOR == swarm ]]; then
        chris_store=$(docker ps -f name=chris_store.1. -q)
        docker exec $chris_store sh -c 'while ! curl -sSf http://localhost:8010/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        chris_store=$(kubectl get pods --selector="app=chris-store,env=production" --output=jsonpath='{.items[*].metadata.name}')
        kubectl exec $chris_store --namespace $NAMESPACE -- sh -c 'while ! curl -sSf http://localhost:8010/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    fi
    windowBottom

    if [ ! -f $STOREBASE/.setup ]; then

        title -d 1 "Creating superuser chris in ChRIS store"
        if [[ $ORCHESTRATOR == swarm ]]; then
            docker exec -it $chris_store sh -c 'python manage.py createsuperuser --username chris --email dev@babymri.org'
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            kubectl exec $chris_store --namespace $NAMESPACE -- sh -c 'python manage.py createsuperuser --username chris --email dev@babymri.org'
        fi
        windowBottom

        title -d 1 "Creating superuser chris in CUBE"
        if [[ $ORCHESTRATOR == swarm ]]; then
            docker exec -it $chris sh -c 'python manage.py createsuperuser --username chris --email dev@babymri.org'
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            kubectl exec $chris --namespace $NAMESPACE -- sh -c 'python manage.py createsuperuser --username chris --email dev@babymri.org'
        fi
        windowBottom

        title -d 1 "Uploading the plugin fnndsc/pl-dircopy"
        if [[ $ORCHESTRATOR == swarm ]]; then
            docker exec $chris_store python plugins/services/manager.py add pl-dircopy chris https://github.com/FNNDSC/pl-dircopy fnndsc/pl-dircopy --descriptorstring "$(docker run --rm fnndsc/pl-dircopy dircopy --json 2> /dev/null)"
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            kubectl exec $chris_store --namespace $NAMESPACE -- python plugins/services/manager.py add pl-dircopy chris https://github.com/FNNDSC/pl-dircopy fnndsc/pl-dircopy --descriptorstring "$(docker run --rm fnndsc/pl-dircopy dircopy --json 2> /dev/null)"
        fi
        windowBottom

        title -d 1 "Uploading the plugin fnndsc/pl-topologicalcopy"
        if [[ $ORCHESTRATOR == swarm ]]; then
            docker exec $chris_store python plugins/services/manager.py add pl-topologicalcopy chris https://github.com/FNNDSC/pl-topologicalcopy fnndsc/pl-topologicalcopy --descriptorstring "$(docker run --rm fnndsc/pl-topologicalcopy topologicalcopy --json 2> /dev/null)"
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            kubectl exec $chris_store --namespace $NAMESPACE -- python plugins/services/manager.py add pl-topologicalcopy chris https://github.com/FNNDSC/pl-topologicalcopy fnndsc/pl-topologicalcopy --descriptorstring "$(docker run --rm fnndsc/pl-topologicalcopy topologicalcopy --json 2> /dev/null)"
        fi
        windowBottom

        title -d 1 "Adding host compute environment"
        if [[ $ORCHESTRATOR == swarm ]]; then
            docker exec $chris python plugins/services/manager.py add host "http://pfcon.remote:5005/api/v1/" --description "Remote compute"
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            kubectl exec $chris --namespace $NAMESPACE -- python plugins/services/manager.py add host "http://pfcon.remote:5005/api/v1/" --description "Remote compute"
        fi
        windowBottom

        title -d 1 "Registering pl-dircopy from store to CUBE"
        if [[ $ORCHESTRATOR == swarm ]]; then
            docker exec $chris python plugins/services/manager.py register host --pluginname pl-dircopy
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            kubectl exec $chris --namespace $NAMESPACE -- python plugins/services/manager.py register host --pluginname pl-dircopy
        fi
        windowBottom

        title -d 1 "Registering pl-topologicalcopy from store to CUBE"
        if [[ $ORCHESTRATOR == swarm ]]; then
            docker exec $chris python plugins/services/manager.py register host --pluginname pl-topologicalcopy
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            kubectl exec $chris --namespace $NAMESPACE -- python plugins/services/manager.py register host --pluginname pl-topologicalcopy
        fi
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
        if [[ $STORAGE_TYPE == host ]]; then
            echo "kubectl kustomize kubernetes/prod/overlays/host | envsubst | kubectl delete -f -"  | ./boxes.sh ${LightCyan}
            kubectl kustomize kubernetes/prod/overlays/host | envsubst | kubectl delete -f -
        else
            echo "kubectl kustomize kubernetes/prod/overlays/nfs | envsubst | kubectl delete -f -"  | ./boxes.sh ${LightCyan}
            kubectl kustomize kubernetes/prod/overlays/nfs | envsubst | kubectl delete -f -
        fi
    fi
    windowBottom
fi