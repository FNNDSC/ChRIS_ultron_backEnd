#!/bin/bash
#
# NAME
#
#   make.sh
#
# SYNPOSIS
#
#   make.sh                     [-h] [-i] [-s] [-U] [-I]        \
#                               [-O <swarm|kubernetes>]         \
#                               [-p <hostIp>]                   \
#                               [-S <storeBase>]                \
#                               [local|fnndsc[:dev]]
#
# DESC
#
#   'make.sh' is the main entry point for instantiating a complete backend dev
#   environment.
#
#   Using appropriate flags, this script can skip various introductory/informational
#   steps, deploy ancillary pfcon/pman services on Docker Swarm or Kubernetes, toggle
#   unit/integration testing on or off and even not attach an interactive terminal to
#   the main chris_dev service.
#
# TYPICAL CASES:
#
#  ┌─────────────────────────────────────┐
#  │ Most of the time, you will do this: │
#  ├─────────────────────────────────────┴───────────────────────────────────────────────┐
#  │ Skip unit and integration tests and start backend in daemon mode on a SWARM cluster │
#  │ (the "dev" way when you want to test new plugins etc):                              │
#  └─────────────────────────────────────────────────────────────────────────────────────┘
#
#    THIS IS ONLY THE CASE FOR A SWARM CLUSTER-- which is a typical dev case:
#    To totally tear down the cluster and start fresh:
#
#    docker swarm leave --force && docker swarm init --advertise-addr 127.0.0.1 &&      \
#    ./unmake.sh && sudo rm -fr CHRIS_REMOTE_FS && rm -fr CHRIS_REMOTE_FS &&            \
#    ./make.sh -U -I -i
#
#   Run full CUBE instantiation with tests (the "real-do-only-once" way
#   to be sure the system actually works on your env) on Swarm:
#
#       ./unmake.sh ; sudo rm -fr CHRIS_REMOTE_FS; rm -fr CHRIS_REMOTE_FS; ./make.sh
#
#   Skip unit and integration tests and skip the intro
#   (the "quick-n-dirty" way -- when you are deep in dev mode and
#   restarting the system for the 50th time on a Monday morning):
#
# ./unmake.sh ; sudo rm -fr CHRIS_REMOTE_FS; rm -fr CHRIS_REMOTE_FS; ./make.sh -U -I -i -s
#
#   NOTE: What's up with the "sudo rm..." followed by "rm ..."?
#
#         This is a rather unintuitive work around if ChRIS is being
#         instantiated on a NFS mounted volume (with the `rootsquash`
#         set). Files down directory trees created by running ChRIS
#         dockerized services might have mixed ownership and trying
#         to delete these files as `root` on the host running the
#         service might not remove files owned by a different user.
#
#         Hence this rather counter-intuitive construct where sometimes
#         being `root` is not sufficient in deleting leftover files or
#         directories.
##
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
#   -p <hostIp>
#
#       Explicitly set the IP address of the machine running this script. This parameter
#       is required when the -O flag is set to kubernetes. Not used for swarm.
#
#   -U
#
#       Skip the UNIT tests.
#
#   -I
#
#       Skip the INTEGRATION tests.
#
#   -S <storeBase>
#
#       Explicitly set the STOREBASE dir to <storeBase>. This is the remote ChRIS
#       filesystem where pfcon and plugins share data.
#
#   -i
#
#       Optional do not automatically attach interactive terminal to chris_dev container.
#
#   -s
#
#       Optional skip intro steps. This skips the check on latest versions
#       of containers and the interval version number printing. Makes for
#       slightly faster startup.
#
#   [local|fnndsc[:dev]] (optional, default = 'fnndsc')
#
#       If specified, denotes the container "family" to use.
#
#       If a colon suffix exists, then this is interpreted to further
#       specify the TAG, i.e :dev in the example above.
#
#       The 'fnndsc' family are the containers as hosted on docker hub.
#       Using 'fnndsc' will always attempt to pull the latest container first.
#
#       The 'local' family are containers that are assumed built on the local
#       machine and assumed to exist. The 'local' containers are used when
#       the 'pfcon/pman' services are being locally developed/debugged.
#
#

source ./decorate.sh
source ./cparse.sh

declare -i STEP=0
declare -i b_norestartinteractive_chris_dev=0
declare -i b_skipIntro=0
declare -i b_skipUnitTests=0
declare -i b_skipIntegrationTests=0

ORCHESTRATOR=swarm
HERE=$(pwd)
CREPO=fnndsc
TAG=:latest

if [[ -f .env ]] ; then
    source .env
fi

print_usage () {
    echo "Usage: ./make.sh [-h] [-i] [-s] [-U] [-I] [-O <swarm|kubernetes>] [-p <hostIp>] [-S <storeBase>] [local|fnndsc[:dev]]"
    exit 1
}

while getopts ":hisUIO:p:S:" opt; do
    case $opt in
        h) print_usage
           ;;
        i) b_norestartinteractive_chris_dev=1
          ;;
        s) b_skipIntro=1
          ;;
        U) b_skipUnitTests=1
          ;;
        I) b_skipIntegrationTests=1
          ;;
        O) ORCHESTRATOR=$OPTARG
           if ! [[ "$ORCHESTRATOR" =~ ^(swarm|kubernetes)$ ]]; then
              echo "Invalid value for option -- O"
              print_usage
           fi
           ;;
        p) HOSTIP=$OPTARG
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

if [[ $ORCHESTRATOR == kubernetes ]]; then
    if [ -z ${HOSTIP+x} ]; then
        echo "-p <hostIp> (this machine's ip address) must be specified or the shell
             environment variable HOSTIP must be set when using kubernetes orchestrator"
        print_usage
    fi
fi

if (( $# == 1 )) ; then
    REPO=$1
    export CREPO=$(echo $REPO | awk -F \: '{print $1}')
    export TAG=$(echo $REPO | awk -F \: '{print $2}')
    if (( ${#TAG} )) ; then
        TAG=":$TAG"
    fi
fi

declare -a A_CONTAINER=(
    "fnndsc/chris:dev^CHRISREPO"
    "fnndsc/chris_store^STOREREPO"
    "fnndsc/pfcon${TAG}^PFCONREPO"
    "fnndsc/pman${TAG}^PMANREPO"
    "fnndsc/docker-swift-onlyone^SWIFTREPO"
)

title -d 1 "Setting global exports..."
    if [[ $ORCHESTRATOR == kubernetes ]]; then
        echo -e "HOSTIP=$HOSTIP "                  | ./boxes.sh
        echo -e "exporting REMOTENETWORK=false "   | ./boxes.sh
        export REMOTENETWORK=false
        echo -e "exporting PFCONDNS=pfcon.remote " | ./boxes.sh
        export PFCONDNS=pfcon.remote
        echo -e "exporting PFCONIP=$HOSTIP "       | ./boxes.sh
        export PFCONIP=$HOSTIP
    fi
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

title -d 1 "Pulling non-'local/' core containers where needed..."   \
            "and creating appropriate .env for docker-compose"
printf "${LightCyan}%40s${Green}%-40s${Yellow}\n"                   \
            "docker pull" " library/mysql"                          | ./boxes.sh
docker pull mysql:5                                                 | ./boxes.sh
echo ""                                                             | ./boxes.sh
printf "${LightCyan}%40s${Green}%-40s${Yellow}\n"                   \
            "docker pull " "library/rabbitmq"                       | ./boxes.sh
docker pull rabbitmq:3                                              | ./boxes.sh
if (( ! b_skipIntro )) ; then
    echo "# Variables declared here are available to"               > .env
    echo "# docker-compose on execution"                            >>.env
    for CORE in ${A_CONTAINER[@]} ; do
        cparse $CORE "REPO" "CONTAINER" "MMN" "ENV"
        echo "${ENV}=${REPO}"                                       >>.env
        if [[ $REPO != "local" ]] ; then
            echo ""                                                 | ./boxes.sh
            CMD="docker pull ${REPO}/$CONTAINER"
            printf "${LightCyan}%40s${Green}%-40s${Yellow}\n"       \
                        "docker pull" " ${REPO}/$CONTAINER"         | ./boxes.sh
            windowBottom
            sleep 1
            echo $CMD | sh                                          | ./boxes.sh -c
        fi
    done
    echo "TAG="                                                     >>.env
fi
windowBottom

if (( ! b_skipIntro )) ; then
    title -d 1 "Will use containers with following version info:"
    for CORE in ${A_CONTAINER[@]} ; do
        cparse $CORE "REPO" "CONTAINER" "MMN" "ENV"
        if [[   $CONTAINER != "chris:dev"            && \
                $CONTAINER != "chris_store"          && \
                $CONTAINER != "docker-swift-onlyone"  ]] ; then
            windowBottom
            CMD="docker run --rm ${REPO}/$CONTAINER --version"
            if [[   $CONTAINER == "pfcon"            || \
                    $CONTAINER == "pman"  ]] ; then
              CMD="docker run --rm --entrypoint $CONTAINER ${REPO}/$CONTAINER --version"
            fi
            Ver=$(echo $CMD | sh | grep Version)
            echo -en "\033[2A\033[2K"
            printf "${White}%40s${Green}%-40s${Yellow}\n"            \
                    "${REPO}/$CONTAINER" " $Ver"                     | ./boxes.sh
        fi
    done
fi

title -d 1 "Changing permissions to 755 on" "$HERE"
    cd $HERE
    echo "chmod -R 755 $HERE"                                      | ./boxes.sh
    chmod -R 755 $HERE
windowBottom

title -d 1 "Checking that STOREBASE directory tree" "$STOREBASE is empty..."
    chmod -R 777 $STOREBASE
    b_FSOK=1
    type -all tree >/dev/null 2>/dev/null
    if (( ! $? )) ; then
        tree $STOREBASE                                                    | ./boxes.sh
        report=$(tree $STOREBASE | tail -n 1)
        if [[ "$report" != "0 directories, 0 files" ]] ; then
            b_FSOK=0
        fi
    else
        report=$(find $STOREBASE 2>/dev/null)
        lines=$(echo "$report" | wc -l)
        if (( lines != 1 )) ; then
            b_FSOK=0
        fi
        echo "lines is $lines"
    fi
    if (( ! b_FSOK )) ; then
        printf "The STOREBASE directory $STOREBASE must be empty!\n"    | ./boxes.sh ${Red}
        printf "Please manually clean it and re-run.\n"      | ./boxes.sh ${Yellow}
        printf "\nThis script will now exit with code '1'.\n\n"                     | ./boxes.sh ${Yellow}
        exit 1
    fi
    printf "${LightCyan}%40s${LightGreen}%40s\n"                    \
                "Tree state" "[ OK ]"                               | ./boxes.sh
windowBottom

if [[ $ORCHESTRATOR == swarm ]]; then
    title -d 1  "Creating overlay network: remote"
    echo "docker network create -d overlay --attachable remote"   | ./boxes.sh ${LightCyan}
    docker network create -d overlay --attachable remote
    windowBottom
fi

title -d 1 "Starting remote pfcon containerized environment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack deploy -c swarm/docker-compose_remote.yml pfcon_stack"   | ./boxes.sh ${LightCyan}
        docker stack deploy -c swarm/docker-compose_remote.yml pfcon_stack
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
      echo "envsubst < kubernetes/pfcon_dev.yaml | kubectl apply -f -"           | ./boxes.sh ${LightCyan}
      envsubst < kubernetes/remote.yaml | kubectl apply -f -
    fi
windowBottom

title -d 1 "Waiting for remote pfcon containers to start running on $ORCHESTRATOR"
    echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
    for i in {1..50}; do
        sleep 5
        if [[ $ORCHESTRATOR == swarm ]]; then
            pfcon=$(docker ps -f name=pfcon_stack_pfcon.1 -q)
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            pfcon=$(kubectl get pods --selector="app=pfcon,env=production" --field-selector=status.phase=Running --output=jsonpath='{.items[*].metadata.name}')
        fi
        if [ -n "$pfcon" ]; then
          echo "Success: pfcon container is running on $ORCHESTRATOR"      | ./boxes.sh ${Green}
          break
        fi
    done
    if [ -z "$pfcon" ]; then
        echo "Error: couldn't start pfcon container on $ORCHESTRATOR"      | ./boxes.sh ${Red}
        exit 1
    fi
windowBottom

title -d 1  "Starting CUBE containerized development environment using "            \
            "./docker-compose_dev.yml"
    echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
    echo "docker-compose -f docker-compose_dev.yml up -d"           | ./boxes.sh ${LightCyan}
    windowBottom
    docker-compose -f docker-compose_dev.yml up -d        >& dc.out > /dev/null
    echo -en "\033[2A\033[2K"
    cat dc.out | sed -E 's/(.{80})/\1\n/g'                          | ./boxes.sh ${LightGreen}
windowBottom

title -d 1 "Waiting until ChRIS database server is ready to accept connections..."
    echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
    windowBottom
    docker-compose -f docker-compose_dev.yml        \
        exec chris_dev_db sh -c                     \
        'while ! mysqladmin -uroot -prootp status 2> /dev/null; do sleep 5; done;' >& dc.out > /dev/null
    echo -en "\033[2A\033[2K"
    sed -E 's/[[:alnum:]]+:/\n&/g' dc.out | ./boxes.sh
    echo "Granting <chris> user all DB permissions...."             | ./boxes.sh ${LightCyan}
    echo "This is required for the Django tests."                   | ./boxes.sh ${LightCyan}
    docker-compose -f docker-compose_dev.yml        \
        exec chris_dev_db mysql -uroot -prootp -e   \
        'GRANT ALL PRIVILEGES ON *.* TO "chris"@"%"' >& dc.out > /dev/null
    cat dc.out                                                      | ./boxes.sh
windowBottom

title -d 1 "Waiting until CUBE is ready to accept connections..."
    echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
    windowBottom
    docker-compose -f docker-compose_dev.yml        \
        exec chris_dev sh -c                        \
        'while ! curl -sSf http://localhost:8000/api/v1/users/ 2> /dev/null; do sleep 5; done;' > dc.out
    echo -en "\033[2A\033[2K"
    cat dc.out | python -m json.tool 2>/dev/null                    | ./boxes.sh ${LightGreen}
    echo ""                                                         | ./boxes.sh
    echo "Ready to accept connections"                              | ./boxes.sh ${LightGreen}
    echo ""                                                         | ./boxes.sh
windowBottom

title -d 1 "Waiting until remote pfcon is ready to accept connections..."
    echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
    windowBottom
    docker-compose -f docker-compose_dev.yml        \
        exec chris_dev sh -c                        \
        'while ! curl -sSf http://pfcon.remote:30005/api/v1/ 2> /dev/null; do sleep 5; done;' > dc.out
    echo -en "\033[2A\033[2K"
    cat dc.out | python -m json.tool 2>/dev/null                    | ./boxes.sh ${LightGreen}
    echo ""                                                         | ./boxes.sh
    echo "Ready to accept connections"                              | ./boxes.sh ${LightGreen}
    echo ""                                                         | ./boxes.sh
windowBottom

if (( ! b_skipUnitTests )) ; then
    title -d 1 "Running CUBE Unit tests..."
    echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
    windowBottom
    docker-compose -f docker-compose_dev.yml    \
        exec chris_dev python manage.py         \
        test --exclude-tag integration
    status=$?
    title -d 1 "CUBE Unit tests' results"
    if (( $status == 0 )) ; then
        printf "%40s${LightGreen}%40s${NC}\n"                       \
            "CUBE Unit tests" "[ success ]"                         | ./boxes.sh
    else
        printf "%40s${Red}%40s${NC}\n"                              \
            "CUBE Unit tests" "[ failure ]"                         | ./boxes.sh
    fi
    windowBottom
fi

if (( ! b_skipIntegrationTests )) ; then
    title -d 1 "Running CUBE Integration tests..."
    echo "This might take more than a few minutes... please be patient."    | ./boxes.sh ${Yellow}
    windowBottom
    docker-compose -f docker-compose_dev.yml    \
        exec chris_dev python manage.py         \
        test --tag integration
    status=$?
    title -d 1 "CUBE Integration tests' results"
    if (( $status == 0 )) ; then
        printf "%40s${LightGreen}%40s${NC}\n"                       \
            "CUBE Integration tests" "[ success ]"                  | ./boxes.sh
    else
        printf "%40s${Red}%40s${NC}\n"                              \
            "CUBE Integration tests" "[ failure ]"                  | ./boxes.sh
    fi
    windowBottom
fi

title -d 1 "Waiting until ChRIS store is ready to accept connections..."
    echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
    windowBottom
    docker-compose -f docker-compose_dev.yml    \
        exec chris_store sh -c                   \
        'while ! curl -sSf http://localhost:8010/api/v1/users/ 2> /dev/null; do sleep 5; done;' > dc.out
    echo -en "\033[2A\033[2K"
    cat dc.out | python -m json.tool 2>/dev/null                    | ./boxes.sh ${LightGreen}
    echo ""                                                         | ./boxes.sh
    echo "Ready to accept connections"                              | ./boxes.sh ${LightGreen}
    echo ""                                                         | ./boxes.sh
windowBottom

###
### Create two ChRIS STORE API users using a helper script
###
# Note, emails and user names MUST be unique. Creating a new user
# with the same email as an existing one will throw an error!
#
# Also, '-U' creates a 'superuser' and a '-S' denotes a ChRIS Store
# user (otherwise a ChRIS/CUBE user is assumed).
###
STEP=$(expr $STEP + 1 )
./user_add.sh -s $STEP -U -S " chris:chris1234:dev@babymri.org,                \
                            cubeadmin:cubeadmin1234:cubeadmin@babymri.org"

###
### Create two ChRIS API users using a helper script
###
# Note, emails and user names MUST be unique. Creating a new user
# with the same email as an existing one will throw an error!
#
# Also, '-U' creates a 'superuser'
###
STEP=$(expr $STEP + 1 )
./user_add.sh -s $STEP -U 'chris:chris1234:dev@babymri.org'
STEP=$(expr $STEP + 1 )
# This creates a 'normaluser' (note there is no '-U').
./user_add.sh -s $STEP 'cube:cube1234:cube@babymri.org'

###
### Add plugins to the system using a helper script
###
STEP=$(expr $STEP + 1 )
./plugin_add.sh -s $STEP "\
                    fnndsc/pl-simplefsapp,                      \
                    fnndsc/pl-simpledsapp,                      \
                    fnndsc/pl-s3retrieve,                       \
                    fnndsc/pl-dircopy,                            \
                    fnndsc/pl-topologicalcopy
"

STEP=$(expr $STEP + 4 )
title -d 1 "Automatically creating two unlocked pipelines in the ChRIS STORE" \
                        "(unmutable and available to all users)"
    S3_PLUGIN_VER=$(docker run --rm fnndsc/pl-s3retrieve s3retrieve --version)
    SIMPLEDS_PLUGIN_VER=$(docker run --rm fnndsc/pl-simpledsapp simpledsapp --version)

    PIPELINE_NAME="s3retrieve_v${S3_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}"
    printf "%20s${LightBlue}%60s${NC}\n"                            \
                "Creating pipeline..." "[ $PIPELINE_NAME ]"         | ./boxes.sh
    STR1='[{"plugin_name": "pl-s3retrieve", "plugin_version": "'
    STR2='", "plugin_parameter_defaults": [{"name": "bucket", "default": "somebucket"}, {"name": "awssecretkey", "default": "somekey"},
    {"name": "awskeyid", "default": "somekeyid"}], "previous_index": null}, {"plugin_name": "pl-simpledsapp", "plugin_version": "'
    STR3='", "previous_index": 0}]'
    PLUGIN_TREE=${STR1}${S3_PLUGIN_VER}${STR2}${SIMPLEDS_PLUGIN_VER}${STR3}
    windowBottom
    docker-compose -f docker-compose_dev.yml                        \
        exec chris_store python pipelines/services/manager.py       \
        add "${PIPELINE_NAME}" cubeadmin "${PLUGIN_TREE}" --unlock

    PIPELINE_NAME="simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}"
    echo -en "\033[2A\033[2K"
    printf "%20s${LightBlue}%60s${NC}\n"                            \
                "Creating pipeline..." "[ $PIPELINE_NAME ]"         | ./boxes.sh
    STR4='[{"plugin_name": "pl-simpledsapp", "plugin_version": "'
    STR5='", "previous_index": null},{"plugin_name": "pl-simpledsapp", "plugin_version": "'
    STR6='", "previous_index": 0},{"plugin_name": "pl-simpledsapp", "plugin_version": "'
    STR7='", "previous_index": 0}]'
    PLUGIN_TREE=${STR4}${SIMPLEDS_PLUGIN_VER}${STR5}${SIMPLEDS_PLUGIN_VER}${STR6}${SIMPLEDS_PLUGIN_VER}${STR7}
    windowBottom
    docker-compose -f docker-compose_dev.yml                        \
        exec chris_store python pipelines/services/manager.py       \
        add "${PIPELINE_NAME}" cubeadmin "${PLUGIN_TREE}" --unlock
    echo -en "\033[2A\033[2K"
windowBottom

title -d 1 "Automatically creating a locked pipeline in CUBE"       \
        "(mutable by the owner and not available to other users)"
    PIPELINE_NAME="s3retrieve_v${S3_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}_1"
    printf "%20s${LightBlue}%60s${NC}\n"                            \
                "Creating pipeline..." "[ $PIPELINE_NAME ]"         | ./boxes.sh
    PLUGIN_TREE=${STR1}${S3_PLUGIN_VER}${STR2}${SIMPLEDS_PLUGIN_VER}${STR3}
    windowBottom
    docker-compose -f docker-compose_dev.yml                        \
        exec chris_dev                                              \
        python pipelines/services/manager.py add "${PIPELINE_NAME}" cube "${PLUGIN_TREE}" >& dc.out >/dev/null
    echo -en "\033[2A\033[2K"
    cat dc.out | ./boxes.sh
windowBottom

title -d 1 "Automatically creating an unlocked pipeline in CUBE" "(unmutable and available to all users)"
    PIPELINE_NAME="simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}"
    printf "%20s${LightBlue}%60s${NC}\n"                            \
                "Creating pipeline..." "[ $PIPELINE_NAME ]"         | ./boxes.sh
    PLUGIN_TREE=${STR4}${SIMPLEDS_PLUGIN_VER}${STR5}${SIMPLEDS_PLUGIN_VER}${STR6}${SIMPLEDS_PLUGIN_VER}${STR7}
    windowBottom
    docker-compose -f docker-compose_dev.yml                        \
        exec chris_dev                                              \
        python pipelines/services/manager.py add "${PIPELINE_NAME}" cube "${PLUGIN_TREE}" --unlock >& dc.out >/dev/null
    echo -en "\033[2A\033[2K"
    cat dc.out | ./boxes.sh
windowBottom

title -d 1 "Restarting CUBE's Django development server..."
    printf "${LightCyan}%40s${LightGreen}%40s\n"                \
                "Restarting" "chris_dev"                        | ./boxes.sh
    windowBottom
    docker-compose -f docker-compose_dev.yml restart chris_dev >& dc.out >/dev/null
    echo -en "\033[2A\033[2K"
    cat dc.out | ./boxes.sh
windowBottom

if (( !  b_norestartinteractive_chris_dev )) ; then
    title -d 1 "Attaching interactive terminal (ctrl-c to detach)"
    chris_dev=$(docker ps -f name=chris_dev_1 -q)
    docker attach --detach-keys ctrl-c $chris_dev
fi
