#!/bin/bash
#
# NAME
#
#   unmake.sh
#
# SYNPOSIS
#
#   unmake.sh                     [-O <swarm|kubernetes>]
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
#   -O <swarm|kubernetes>
#
#       Explicitly set the orchestrator. Default is swarm.
#
#

source ./decorate.sh

declare -i STEP=0
ORCHESTRATOR=swarm

print_usage () {
    echo "Usage: ./unmake.sh [-O <swarm|kubernetes>]"
    exit 1
}

while getopts ":O:" opt; do
    case $opt in
        O) ORCHESTRATOR=$OPTARG
           if ! [[ "$ORCHESTRATOR" =~ ^(swarm|kubernetes)$ ]]; then
              echo "Invalid value for option -- O"
              print_usage
           fi
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

if [[ $ORCHESTRATOR == kubernetes ]]; then
    title -d 1 "Setting global exports..."
    echo -e "exporting REMOTENETWORK=false " | ./boxes.sh
    export REMOTENETWORK=false
    windowBottom
fi

title -d 1 "Destroying remote pfcon containerized environment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack rm pfcon_stack"                               | ./boxes.sh ${LightCyan}
        docker stack rm pfcon_stack
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        echo "kubectl delete -f kubernetes/remote.yaml"                  | ./boxes.sh ${LightCyan}
        kubectl delete -f kubernetes/remote.yaml
    fi
    echo "Removing ./FS tree"                                            | ./boxes.sh
    rm -fr ./FS
windowBottom

title -d 1 "Destroying CUBE containerized development environment" "from  ./docker-compose_dev.yml"
    echo "Do you want to also remove persistent volumes? [y/n]"             | ./boxes.sh
    windowBottom
    old_stty_cfg=$(stty -g)
    stty raw -echo ; REPLY=$(head -c 1) ; stty $old_stty_cfg
    echo -en "\033[2A\033[2K"
    # read -p  " " -n 1 -r REPLY
    if [[ $REPLY =~ ^[Yy]$ ]] ; then
        printf "Removing persistent volumes...\n"                           | ./boxes.sh ${Yellow}
        echo "This might take a few minutes... please be patient."          | ./boxes.sh ${Yellow}
        windowBottom
        docker-compose -f docker-compose_dev.yml down -v >& dc.out >/dev/null
        echo -en "\033[2A\033[2K"
        cat dc.out | ./boxes.sh
        echo "Removing ./FS tree"                                           | ./boxes.sh
        rm -fr ./FS
    else
        printf "Keeping persistent volumes...\n"                            | ./boxes.sh ${Yellow}
        echo "This might take a few minutes... please be patient."          | ./boxes.sh ${Yellow}
        windowBottom
        docker-compose -f docker-compose_dev.yml down >& dc.out >/dev/null
        echo -en "\033[2A\033[2K"
        cat dc.out | ./boxes.sh
    fi
windowBottom

if [[ $ORCHESTRATOR == swarm ]]; then
    title -d 1 "Removing overlay network: remote"
    sleep 3
    docker network rm remote
    windowBottom
fi
