#!/bin/bash
#
# NAME
#
#   unmake.sh
#
# SYNPOSIS
#
#   unmake.sh                     [-h]
#                                 [-O <swarm|kubernetes>]
#                                 [-S <storeBase>]
#
#
# DESC
#
#   'unmake.sh' destroys a chris development instance with remote ancillary services
#   pfcon/pman running on Swarm or Kubernetes.
#
# TYPICAL CASES:
#
#   Destroy chris_dev instance with remote ancillary services running on Swarm:
#
#       unmake.sh
#
#   Destroy chris_dev instance with remote ancillary services running on Kubernetes:
#
#       unmake.sh -O kubernetes
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
#       filesystem where pfcon and plugins share data.
#
#

source ./decorate.sh

declare -i STEP=0
ORCHESTRATOR=swarm

dc_check () {
    STATUS=$1
    if [[ $STATUS != "0" ]] ; then
        echo -en "\033[2A\033[2K"
        cat dc.out | sed -E 's/(.{80})/\1\n/g'                      | ./boxes.sh LightRed
    else
        echo -en "\033[2A\033[2K"
        cat dc.out                                                  | ./boxes.sh White
    fi
}

print_usage () {
    echo "Usage: ./unmake.sh [-h] [-O <swarm|kubernetes>] [-S <storeBase>]"
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

title -d 1 "Setting global exports"
    boxcenter "-= ORCHESTRATOR =-"
    boxcenter "$ORCHESTRATOR"                                                    LightCyan
    boxcenter ""
    if [ -z ${STOREBASE+x} ]; then
        STOREBASE=$(pwd)/CHRIS_REMOTE_FS
    fi
    boxcenter "-= STOREBASE =-"
    if (( ${#STOREBASE} > 80 )) ; then
        STOREBASEdisp="...${STOREBASE: -77}"
    else
        STOREBASEdisp=$STOREBASE
    fi
    echo "$STOREBASEdisp"                                               | ./boxes.sh LightCyan
    export STOREBASE=$STOREBASE

    if [[ $ORCHESTRATOR == kubernetes ]]; then
        echo -e "exporting REMOTENETWORK=false "                    | ./boxes.sh
        export REMOTENETWORK=false
    windowBottom
fi
windowBottom

title -d 1 "Destroying remote pfcon containerized environment on " \
                                "-= $ORCHESTRATOR =-"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "$ docker stack rm pfcon_stack"                        | ./boxes.sh LightCyan
        windowBottom
        docker stack rm pfcon_stack &> dc.out
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        echo "$ kubectl delete -f kubernetes/remote.yaml"           | ./boxes.sh LightCyan
        windowBottom
        kubectl delete -f kubernetes/remote.yaml &> dc.out
    fi
    dc_check $?
    echo "$ rm -fr \$STOREBASE"                                     | ./boxes.sh LightCyan
    rm -fr $STOREBASE
windowBottom

title -d 1 "Destroying CUBE containerized development environment" \
                        "from  ./docker-compose_dev.yml"
    echo "Do you want to also remove persistent volumes? [y/n]"     | ./boxes.sh White
    windowBottom
    old_stty_cfg=$(stty -g)
    stty raw -echo ; REPLY=$(head -c 1) ; stty $old_stty_cfg
    echo -en "\033[2A\033[2K"
    # read -p  " " -n 1 -r REPLY
    if [[ $REPLY =~ ^[Yy]$ ]] ; then
        boxcenter ""
        echo "Removing persistent volumes... please be patient."    | ./boxes.sh Yellow
        boxcenter ""
        echo "$ docker-compose -f docker-compose_dev.yml down -v"   | ./boxes.sh LightCyan         
        windowBottom
        docker-compose -f docker-compose_dev.yml down -v >& dc.out
        dc_check $?
    else
        echo "Keeping persistent volumes... please be patient."     | ./boxes.sh Yellow
        windowBottom
        docker-compose -f docker-compose_dev.yml down >& dc.out
        dc_check $?
    fi
windowBottom

if [[ $ORCHESTRATOR == swarm ]]; then
    title -d 1 "Removing overlay network: remote"
    windowBottom
    sleep 2
    docker network rm remote &> dc.out
    dc_check $?
    windowBottom
fi
