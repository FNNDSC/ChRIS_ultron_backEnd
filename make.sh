#!/usr/bin/env bash

# If you are on macOS, please make sure that /usr/bin/env bash is NOT the
# default /bin/bash! On macOS bash is effectively deprecated and this script
# will not work!

# TL:DR
quick_n_VeryDirtyStart="
docker swarm leave --force && docker swarm init --advertise-addr 127.0.0.1 &&  \
./unmake.sh && sudo rm -fr CHRIS_REMOTE_FS && rm -fr CHRIS_REMOTE_FS &&        \
./make.sh -U -I -i
"
#
# NAME
#
#   make.sh
#
# SYNPOSIS
#
#   make.sh                     [-h] [-o] [-i] [-s] [-U] [-I]   \
#                               [-O <swarm|kubernetes>]         \
#                               [-F <swift|filesystem>]         \
#                               [-P <hostIp>]                   \
#                               [-S <storeBase>]                \
#                               [local|fnndsc[:dev]]
#
# DESC
#
#   'make.sh' is the main entry point for instantiating a complete backend dev
#   environment.
#
#   Using appropriate flags, this script can skip various introductory or infor-
#   mational steps, deploy ancillary pfcon/pman services on Docker Swarm or
#   Kubernetes, toggle unit/integration testing ON/OFF and/or detach the
#   interactive terminal from the main chris_dev service.
#
# TYPICAL CASES:
#
#  ┌─────────────────────────────────────┐
#  │ Most of the time, you will do this: │
#  ├─────────────────────────────────────┴─────────────────────────────────────┐
#  │ Skip unit and integration tests and start backend in daemon mode on a     │
#  │ SWARM clsuter (the "dev" way when you want to test new plugins etc):      │
#  └───────────────────────────────────────────────────────────────────────────┘
#
#    THIS IS ONLY THE CASE FOR A SWARM CLUSTER-- which is a typical dev case:
#    To totally tear down the cluster and start fresh:
#
#    docker swarm leave --force &&                                             \
#    docker swarm init --advertise-addr 127.0.0.1 &&                           \
#    ./unmake.sh && sudo rm -fr CHRIS_REMOTE_FS && rm -fr CHRIS_REMOTE_FS &&   \
#    ./make.sh -U -I -i
#
#   Run full CUBE instantiation with tests (the "real-do-only-once" way
#   to be sure the system actually works on your env) on Swarm:
#
#  ./unmake.sh ; sudo rm -fr CHRIS_REMOTE_FS; rm -fr CHRIS_REMOTE_FS; ./make.sh
#
#    Run full CUBE instantiation using filesystem storage:
#
#  ./unmake.sh -F filesystem; sudo rm -fr CHRIS_REMOTE_FS; rm -fr CHRIS_REMOTE_FS; ./make.sh -F filesystem
#
#    Run full CUBE instantiation using fslink (filesystem with support for ChRIS links) storage:
#
#  ./unmake.sh -F fslink; sudo rm -fr CHRIS_REMOTE_FS; rm -fr CHRIS_REMOTE_FS; ./make.sh -F fslink
#
#   Skip unit and integration tests and skip the intro
#   (the "quick-n-dirty" way -- when you are deep in dev mode and
#   restarting the system for the 50th time on a Monday morning):
#
#  ./unmake.sh
#  sudo rm -fr CHRIS_REMOTE_FS; rm -fr CHRIS_REMOTE_FS; ./make.sh -U -I -i -s
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
#   -o
#
#       Optional execute the remote PFCON in out-of-network mode. Default is to execute
#       PFCON in-network with Swift as the shared storage between CUBE and PFCON.
#
#   -F <swift|fslink|filesystem>]
#
#       Explicitly set the storage environment. Default is swift.
#
#   -O <swarm|kubernetes>
#
#       Explicitly set the orchestrator. Default is swarm.
#
#   -P <hostIp>
#
#       Explicitly set the IP address of the machine running this script. This
#       parameter is required when the -O flag is set to kubernetes. Not used
#       for swarm.
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
#       Explicitly set the STOREBASE dir to <storeBase>. This is the remote
#       ChRIS filesystem where pfcon and plugins share data.
#
#   -i
#
#       Optional do not automatically attach interactive terminal to chris_dev
#       container.
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
declare -i b_pfconInNetwork=1

ORCHESTRATOR=swarm
STORAGE_ENV=swift
HERE=$(pwd)
CREPO=fnndsc

if [[ -f .env ]] ; then
    source .env
fi

catw() {
    FILE=$1
    COLOR=$2
    if (( !${#COLOR} )) ; then
        COLOR=White
    fi
    if [[ -f $FILE ]] ; then
        cat dc.out                                                      |\
        sed 's/[[:alnum:]]+:/\n&/g'                                     |\
        sed -E 's/(.{80})/\1\n/g'                                       | ./boxes.sh $COLOR
    fi
}

dc_check () {
    STATUS=$1
    DCECHO=$2
    thisStatusCheckOK=0
    if [[ $STATUS != "0" ]] ; then
        if (( ${#DCECHO} )) ; then
            echo -en "\033[2A\033[2K"
            catw dc.out LightRed
        else
            echo -en "\033[3A\033[2K"
        fi
    else
        thisStatusCheckOK=1
        if (( ${#DCECHO} )) ; then
            echo -en "\033[2A\033[2K"
            catw dc.out White
        else
            echo -en "\033[3A\033[2K"
        fi
    fi
}

dc_check_code () {
    STATUS=$1
    CODE=$2
    DCECHO=$3
    if (( $CODE > 1 )) ; then
        if [[ ${#DCECHO} ]] ; then
            echo -en "\033[2A\033[2K"
            catw dc.out LightRed
        else
            echo -en "\033[3A\033[2K"
        fi
    else
        if [[ ${#DCECHO} ]] ; then
            echo -en "\033[2A\033[2K"
            catw dc.out White
        else
            echo -en "\033[3A\033[2K"
        fi
    fi
}

print_usage () {
    echo "Usage: ./make.sh [-h] [-o] [-i] [-s] [-U] [-I] [-O <swarm|kubernetes>] [-F <swift|fslink|filesystem>] [-P <hostIp>] [-S <storeBase>] [local|fnndsc[:dev]]"
    exit 1
}

while getopts ":hoisUIO:F:P:S:" opt; do
    case $opt in
        h) print_usage
           ;;
        o) b_pfconInNetwork=0
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
        F) STORAGE_ENV=$OPTARG
           if ! [[ "$STORAGE_ENV" =~ ^(swift|fslink|filesystem)$ ]]; then
              echo "Invalid value for option -- F"
              print_usage
           fi
           ;;
        P) HOSTIP=$OPTARG
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
        echo "-P <hostIp> (this machine's ip address) must be specified or the shell
             environment variable HOSTIP must be set when using kubernetes orchestrator
             If you are using minikube to run the development environment, HOSTIP can be gotten by running
             'minikube ip' on the terminal"
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

rm -f dc.out ; title -d 1 "Setting global exports"
    boxcenter "-= ORCHESTRATOR =-"
    boxcenter "$ORCHESTRATOR"                                                    LightCyan
    boxcenter ""

    if (( b_pfconInNetwork )) ; then
        boxcenter "exporting STORAGE_ENV=$STORAGE_ENV "
        export STORAGE_ENV=$STORAGE_ENV
        boxcenter ""
        boxcenter "exporting PFCON_INNETWORK=true "
        export PFCON_INNETWORK=true
    else
        boxcenter "-= STORAGE_ENV =-"
        boxcenter "$STORAGE_ENV"                                                    LightCyan
        boxcenter ""
        boxcenter "exporting PFCON_INNETWORK=false "
        export PFCON_INNETWORK=false
    fi
    boxcenter ""
    if [[ $ORCHESTRATOR == kubernetes ]]; then
        echo -e "HOSTIP=$HOSTIP"                   | ./boxes.sh
        echo -e "exporting REMOTENETWORK=false "   | ./boxes.sh
        export REMOTENETWORK=false
        echo -e "exporting MINIKUBENETWORK=true"
        export MINIKUBENETWORK=true
        echo -e "exporting PFCONDNS=pfcon.remote " | ./boxes.sh
        export PFCONDNS=pfcon.remote
        boxcenter "exporting PFCONIP=$HOSTIP "
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
    if (( ${#STOREBASE} > 80 )) ; then
        STOREBASEdisp="...${STOREBASE: -77}"
    else
        STOREBASEdisp=$STOREBASE
    fi
    boxcenter "-= STOREBASE =-"
    echo "${STOREBASEdisp}"                                               | ./boxes.sh LightCyan
    export STOREBASE=$STOREBASE

    export UID=$(id -u) GID=$(id -g)
windowBottom

rm -f dc.out ; title -d 1 "Pulling non-'local/' core containers where needed"      \
            "and creating appropriate .env for docker-compose"

    printf "${LightCyan}%13s${Green}%-67s${Yellow}\n"               \
            "$ docker pull" " library/postgres"                     | ./boxes.sh
    windowBottom
    docker pull postgres:16 >& dc.out
    dc_check $? "PRINT"
    echo ""                                                         | ./boxes.sh
    printf "${LightCyan}%13s${Green}%-67s${Yellow}\n"               \
            "$ docker pull" " library/rabbitmq"                     | ./boxes.sh
    windowBottom
    docker pull rabbitmq:3 >& dc.out
    dc_check $? "PRINT"

    if (( ! b_skipIntro )) ; then
        echo "# Variables declared here are available to"               > .env
        echo "# docker-compose on execution"                            >>.env
        for CORE in ${A_CONTAINER[@]} ; do
            cparse $CORE "REPO" "CONTAINER" "MMN" "ENV"
            echo "${ENV}=${REPO}"                                       >>.env
            if [[ $REPO != "local" && $CONTAINER != "chris:dev" ]] ; then
                echo ""                                             | ./boxes.sh
                CMD="docker pull ${REPO}/$CONTAINER"
                printf "${LightCyan}%13s${Green}%-67s${Yellow}\n"   \
                        "$ docker pull" " ${REPO}/$CONTAINER"       | ./boxes.sh
                windowBottom
                $CMD  >& dc.out
                # sleep 1
                dc_check $? "PRINT"
            fi
        done
        echo "TAG="                                                     >>.env
    fi
windowBottom

if (( ! b_skipIntro )) ; then
    rm -f dc.out ; title -d 1 "Ancillary services version info:"
    boxcenter ""
    for CORE in ${A_CONTAINER[@]} ; do
        cparse $CORE "REPO" "CONTAINER" "MMN" "ENV"
        if [[   $CONTAINER != "chris:dev"            && \
                $CONTAINER != "chris_store"          && \
                $CONTAINER != "docker-swift-onlyone"  ]] ; then
            CMD="docker run --rm ${REPO}/$CONTAINER --version"
            if [[   $CONTAINER == "pfcon"            || \
                    $CONTAINER == "pman"  ]] ; then
              CMD="docker inspect -f '{{ (index .Config.Labels \"org.opencontainers.image.version\") }}' $REPO/$CONTAINER"
            fi
            echo "$ $CMD"                                           | ./boxes.sh LightCyan
            windowBottom
            sh -c "$CMD" >& dc.out
            dc_check_code $? 1 "PRINT"
        fi
    done
fi
boxcenter ""
windowBottom

rm -f dc.out ; title -d 1 "Changing permissions to 755 on" "$HERE"
    cd $HERE
    echo "$ chmod -R 755 $HERE"                                     | ./boxes.sh LightCyan
    windowBottom
    chmod -R 755 $HERE &> dc.out
    dc_check $? "PRINT"
windowBottom

rm -f dc.out ; title -d 1 "Checking that STOREBASE directory tree is empty" "${STOREBASE}"
    chmod -R 777 $STOREBASE
    b_FSOK=1
    type -all tree >/dev/null 2>/dev/null
    if (( ! $? )) ; then
        tree $STOREBASE                                             | ./boxes.sh
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
    fi
    if (( ! b_FSOK )) ; then
        boxcenter "The STOREBASE directory must be empty!"                      LightRed
        boxcenter ""
        boxcenter "Please manually clean it and re-run."                        Yellow
        boxcenter "This script will now exit with code '1'."                    Yellow
        windowBottom
        exit 1
    fi
    printf "${LightCyan}%40s${LightGreen}%40s\n"                    \
                "Tree state" "[ OK ]"                               | ./boxes.sh
windowBottom

if [[ $ORCHESTRATOR == swarm ]]; then
    rm -f dc.out ; title -d 1  "Creating overlay network: remote"
    echo "$ docker network create -d overlay --attachable remote"   | ./boxes.sh LightCyan
    windowBottom
    docker network create -d overlay --attachable remote            >& dc.out
    dc_check $? "PRINT"
    windowBottom
fi

rm -f dc.out ; title -d 1 "Starting remote pfcon containerized environment on"     \
                                "-= $ORCHESTRATOR =-"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "$ docker stack deploy -c swarm/docker-compose_remote.yml pfcon_stack"\
                        | ./boxes.sh LightCyan
        windowBottom
        docker stack deploy -c swarm/docker-compose_remote.yml pfcon_stack >& dc.out
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
      echo "$ envsubst < kubernetes/pfcon_dev.yaml | kubectl apply -f -" \
                        | ./boxes.sh LightCyan
      windowBottom
      envsubst < kubernetes/remote.yaml | kubectl apply -f - >& dc.out
    fi
    dc_check $? "PRINT"
windowBottom

rm -f dc.out ; title -d 1 "Waiting for remote pfcon containers to start running on"\
                                "-= $ORCHESTRATOR =-"
    echo "Starting pfcon... please be patient."                     | ./boxes.sh Yellow
    windowBottom
    for i in {1..10}; do
        sleep 5
        if [[ $ORCHESTRATOR == swarm ]]; then
            pfcon=$(docker ps -f name=pfcon_stack_pfcon.1 -q)
        elif [[ $ORCHESTRATOR == kubernetes ]]; then
            pfcon=$(kubectl get pods --selector="app=pfcon,env=production"     \
                        --field-selector=status.phase=Running                  \
                        --output=jsonpath='{.items[*].metadata.name}')
        fi
        if [ -n "$pfcon" ]; then
          echo -en "\033[3A\033[2K"
          boxcenter ""
          boxcenter "Success: pfcon container is running on $ORCHESTRATOR"      LightGreen
          boxcenter ""
          break
        fi
    done
    if [ -z "$pfcon" ]; then
        echo -en "\033[3A\033[2K"
        boxcenter
        boxcenter "Error: couldn't start pfcon container on $ORCHESTRATOR" Red
        boxcenter "This script will now terminate with exit code '2'."     Red
        boxcenter
        windowBottom
        exit 2
    fi
windowBottom

if [[ $STORAGE_ENV == 'swift' ]]; then
    rm -f dc.out ; title -d 1  "Starting CUBE containerized development environment using "            \
                        "./docker-compose_dev.yml"
        echo "This might take a few minutes... please be patient."      | ./boxes.sh Yellow
        echo "$ docker compose -f docker-compose_dev.yml up -d --build" | ./boxes.sh LightCyan
        windowBottom
        docker compose -f docker-compose_dev.yml up -d --build  >& dc.out
        dc_check $? "PRINT"
    windowBottom
elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
    rm -f dc.out ; title -d 1  "Starting CUBE containerized development environment using "            \
                            "./docker-compose_noswift.yml"
        echo "This might take a few minutes... please be patient."      | ./boxes.sh Yellow
        echo "$ docker compose -f docker-compose_noswift.yml up -d --build" | ./boxes.sh LightCyan
        windowBottom
        docker compose -f docker-compose_noswift.yml up -d --build  >& dc.out
        dc_check $? "PRINT"
    windowBottom
fi

rm -f dc.out ; title -d 1 "Waiting until ChRIS database server is ready to accept connections"
    echo "This might take a few minutes... please be patient."      | ./boxes.sh Yellow
    windowBottom
    if [[ $STORAGE_ENV == 'swift' ]]; then
        docker compose -f docker-compose_dev.yml        \
            exec chris_dev_db sh -c                     \
            'while ! psql -U chris -d chris_dev -c "select 1" > dc.out 2> /dev/null; do sleep 5; done;'
    elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
        docker compose -f docker-compose_noswift.yml        \
            exec chris_dev_db sh -c                     \
            'while ! psql -U chris -d chris_dev -c "select 1" > dc.out 2> /dev/null; do sleep 5; done;'
    fi
    dc_check $? "PRINT"
    echo ""                                                         | ./boxes.sh
    boxcenter "ChRIS database is ready to accept connections"                    LightGreen
    echo ""                                                         | ./boxes.sh
windowBottom

rm -f dc.out ; title -d 1 "Waiting until CUBE is ready to accept connections"
    echo "This might take a few minutes... please be patient."      | ./boxes.sh Yellow
    windowBottom
    if [[ $STORAGE_ENV == 'swift' ]]; then
        docker compose -f docker-compose_dev.yml        \
            exec chris_dev sh -c                        \
            'while ! curl -sSf http://localhost:8000/api/v1/users/ >/dev/null 2>/dev/null ; do sleep 5; done;' \
            > dc.out 2>&1
    elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
        docker compose -f docker-compose_noswift.yml        \
            exec chris_dev sh -c                        \
            'while ! curl -sSf http://localhost:8000/api/v1/users/ >/dev/null 2>/dev/null ; do sleep 5; done;' \
            > dc.out 2>&1
    fi
    dc_check $? "PRINT"
    echo ""                                                         | ./boxes.sh
    boxcenter "CUBE API is ready to accept connections"                          LightGreen
    echo ""                                                         | ./boxes.sh
windowBottom

rm -f dc.out ; title -d 1 "Waiting until remote pfcon is ready to accept connections"
    echo "This might take a few minutes... please be patient."      | ./boxes.sh Yellow
    windowBottom
    if [[ $STORAGE_ENV == 'swift' ]]; then
        docker compose -f docker-compose_dev.yml        \
            exec chris_dev sh -c                        \
            'while ! curl -sSf http://pfcon.remote:30005/api/v1/health/ 2> /dev/null; do
            sleep 5; done;' \
                                    > dc.out
    elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
        docker compose -f docker-compose_noswift.yml        \
            exec chris_dev sh -c                        \
            'while ! curl -sSf http://pfcon.remote:30005/api/v1/health/ 2> /dev/null; do
            sleep 5; done;' \
                                    > dc.out
    fi
    dc_check $? "PRINT"
    echo ""                                                         | ./boxes.sh
    echo ""                                                         | ./boxes.sh
    boxcenter "Remote pfcon is ready to accept connections"                      LightGreen
    echo ""                                                         | ./boxes.sh
windowBottom

if (( ! b_skipUnitTests )) ; then
    rm -f dc.out ; title -d 1 "Running CUBE Unit tests"
    echo "This might take a few minutes... please be patient."      | ./boxes.sh Yellow
    windowBottom
    if [[ $STORAGE_ENV == 'swift' ]]; then
        docker compose -f docker-compose_dev.yml    \
            exec chris_dev python manage.py         \
            test --exclude-tag integration
    elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
        docker compose -f docker-compose_noswift.yml    \
            exec chris_dev python manage.py         \
            test --exclude-tag integration
    fi
    status=$?
    rm -f dc.out ; title -d 1 "CUBE Unit tests' results"
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
    rm -f dc.out ; title -d 1 "Running CUBE Integration tests"
    echo "This might take a while... please be patient."            | ./boxes.sh Yellow
    windowBottom
    if [[ $STORAGE_ENV == 'swift' ]]; then
        docker compose -f docker-compose_dev.yml    \
            exec chris_dev python manage.py         \
            test --tag integration
    elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
        docker compose -f docker-compose_noswift.yml    \
            exec chris_dev python manage.py         \
            test --tag integration
    fi
    status=$?
    rm -f dc.out ; title -d 1 "CUBE Integration tests' results"
    if (( $status == 0 )) ; then
        printf "%40s${LightGreen}%40s${NC}\n"                       \
            "CUBE Integration tests" "[ success ]"                  | ./boxes.sh
    else
        printf "%40s${Red}%40s${NC}\n"                              \
            "CUBE Integration tests" "[ failure ]"                  | ./boxes.sh
    fi
    windowBottom
fi

# Setup users and plugins
if [[ $STORAGE_ENV == 'swift' ]]; then
    docker compose -f docker-compose_dev.yml run --rm chrisomatic
elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
    docker compose -f docker-compose_noswift.yml run --rm chrisomatic
fi

# set compute resource 'host' to operate in-network (workaround until chrisomatic supports it)
if (( b_pfconInNetwork )) ; then
    if [[ $STORAGE_ENV == 'swift' ]]; then
        docker-compose -f docker-compose_dev.yml exec chris_dev /bin/bash -c \
            'python manage.py shell -c "from plugins.models import ComputeResource; cr = ComputeResource.objects.get(name=\"host\"); cr.compute_innetwork = True; cr.save()"'
    elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
        docker-compose -f docker-compose_noswift.yml exec chris_dev /bin/bash -c \
            'python manage.py shell -c "from plugins.models import ComputeResource; cr = ComputeResource.objects.get(name=\"host\"); cr.compute_innetwork = True; cr.save()"'

    fi
fi


STEP=$(expr $STEP + 4 )
rm -f dc.out ; title -d 1 "Automatically creating a locked pipeline in CUBE"       \
        "(mutable by the owner and not available to other users)"
    S3_PLUGIN_VER=$(docker run --rm fnndsc/pl-s3retrieve s3retrieve --version)
    SIMPLEDS_PLUGIN_VER=$(docker run --rm fnndsc/pl-simpledsapp simpledsapp --version)
    PIPELINE_NAME="s3retrieve_v${S3_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}"
    PIPELINE_NAME="s3retrieve_v${S3_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}_1"
    printf "%20s${LightBlue}%60s${NC}\n"                            \
                "Creating pipeline..." "[ $PIPELINE_NAME ]"         | ./boxes.sh
    STR1='[{"title": "pl-s3retrieve", "plugin_name": "pl-s3retrieve", "plugin_version": "'
    STR2='", "plugin_parameter_defaults": [{"name": "bucket", "default": "somebucket"},
      {"name": "awssecretkey", "default": "somekey"},
    {"name": "awskeyid", "default": "somekeyid"}], "previous_index": null, "previous": null},  {"title":
    "pl-simpledsapp", "plugin_name": "pl-simpledsapp", "plugin_version": "'
    STR3='", "previous_index": 0, "previous": "pl-s3retrieve"}]'
    PLUGIN_TREE=${STR1}${S3_PLUGIN_VER}${STR2}${SIMPLEDS_PLUGIN_VER}${STR3}
    windowBottom
    if [[ $STORAGE_ENV == 'swift' ]]; then
        docker compose -f docker-compose_dev.yml                        \
        exec chris_dev                                              \
        python pipelines/services/manager.py add "${PIPELINE_NAME}" \
                cube "${PLUGIN_TREE}" >& dc.out
    elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
        docker compose -f docker-compose_noswift.yml                        \
        exec chris_dev                                              \
        python pipelines/services/manager.py add "${PIPELINE_NAME}" \
                cube "${PLUGIN_TREE}" >& dc.out
    fi
    dc_check $? "PRINT"
windowBottom

rm -f dc.out ; title -d 1 "Automatically creating an unlocked pipeline in CUBE"    \
                "(unmutable and available to all users)"
    PIPELINE_NAME="simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}"
    printf "%20s${LightBlue}%60s${NC}\n"                            \
                "Creating pipeline..." "[ $PIPELINE_NAME ]"         | ./boxes.sh
    STR4='[{"title": "pl-simpledsapp1", "plugin_name": "pl-simpledsapp", "plugin_version": "'
    STR5='", "previous_index": null, "previous": null},{"title": "pl-simpledsapp2", "plugin_name":
    "pl-simpledsapp", "plugin_version": "'
    STR6='", "previous_index": 0, "previous": "pl-simpledsapp1"},{"title": "pl-simpledsapp3", "plugin_name":
    "pl-simpledsapp", "plugin_version": "'
    STR7='", "previous_index": 0, "previous": "pl-simpledsapp1"}]'
    PLUGIN_TREE=${STR4}${SIMPLEDS_PLUGIN_VER}${STR5}${SIMPLEDS_PLUGIN_VER}${STR6}${SIMPLEDS_PLUGIN_VER}${STR7}
    windowBottom
    if [[ $STORAGE_ENV == 'swift' ]]; then
    docker compose -f docker-compose_dev.yml                        \
        exec chris_dev                                              \
        python pipelines/services/manager.py add "${PIPELINE_NAME}" \
        cube "${PLUGIN_TREE}" --unlock >& dc.out
    elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
    docker compose -f docker-compose_noswift.yml                        \
        exec chris_dev                                              \
        python pipelines/services/manager.py add "${PIPELINE_NAME}" \
        cube "${PLUGIN_TREE}" --unlock >& dc.out
    fi
    dc_check $? "PRINT"
windowBottom

rm -f dc.out ; title -d 1 "Restarting CUBE's Django development server"
    printf "${LightCyan}%40s${LightGreen}%40s\n"                \
                "Restarting" "chris_dev"                        | ./boxes.sh
    windowBottom
    if [[ $STORAGE_ENV == 'swift' ]]; then
        docker compose -f docker-compose_dev.yml restart chris_dev >& dc.out
    elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
        docker compose -f docker-compose_noswift.yml restart chris_dev >& dc.out
    fi
    dc_check $?
windowBottom

if (( !  b_norestartinteractive_chris_dev )) ; then
    rm -f dc.out ; title -d 1 "Attaching interactive terminal (ctrl-a to detach)"
    chris_dev=$(docker ps -f name=chris_dev -f ancestor=fnndsc/chris:dev -q)
    docker attach --detach-keys ctrl-a $chris_dev
fi
