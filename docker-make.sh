#!/bin/bash
#
# NAME
#
#   docker-make.sh
#
# SYNPOSIS
#
#   docker-make.sh    [-r <service>]                  \
#                               [-a <swarm-advertise-adr>]      \
#                               [-p] [-s] [-i] [-d]             \
#                               [-U] [-I]                       \
#                               [-S <storeBaseOverride>]        \
#                               [-e <computeEnv>]               \
#                               [local|fnndsc[:dev]]
#
# DESC
# 
#   'docker-make.sh' is the main entry point for instantiating a
#   complete backend dev environment.
#
#   It creates a pattern of directories and symbolic links that reflect the
#   declarative environment of the docker-compose_dev.yml contents.
#
# TYPICAL CASES:
#
#   Run full CUBE instantiation with tests:
#
#       *destroy* ; sudo rm -fr FS; rm -fr FS; *make*
#
#   Skip unit and integration tests and the intro:
#
#       *destroy* ; sudo rm -fr FS; rm -fr FS; *make* -U -I -s
# 
# ARGS
#
#   -U
#
#       Skip the UNIT tests.
#
#   -I
#
#       Skip the INTEGRATION tests.
#
#   -S <storeBaseOverride>
#
#       Explicitly set the STOREBASE dir to <storeBaseOverride>. This is useful
#       mostly in non-Linux hosts (like macOS) where there might be a mismatch
#       between the actual STOREBASE path and the text of the path shared between 
#       the macOS host and the docker VM. 
#
#   -r <service>
#   
#       Restart <service> in interactive mode. This is mainly for debugging
#       and is typically used to restart the 'pfcon', 'pfioh', and 'pman' 
#       services.
#
#   -e <computeEnv>
#
#       Register all plugins to the passed <computeEnv>. Note, this is simply
#       an index string that is actually defined in `pfcon`. In other words,
#       the <computeEnv> here is just a label, and the actual env is fully 
#       specified by `pfcon`.
#
#   -a <swarm-advertise-adr>
#
#       If specified, pass <swarm-advertise-adr> to swarm init.
#
#   -i 
#
#       Optional do not restart final chris_dev in interactive mode. If any
#       sub services have been restarted in interactive mode then this will
#       break the final restart of the chris_dev container. Thus, if any
#       services have been restarted with '-r <service>' it is recommended
#       to also use this flag to avoid the chris_dev restart.
#
#   -s
#
#       Optional skip intro steps. This skips the check on latest versions
#       of containers and the interval version number printing. Makes for
#       slightly faster startup.
#
#   -p
#   
#       Optional pause after instantiating system to allow user to stop
#       and restart services in interactive mode. User stops and restarts
#       services explicitly with
#
#               docker stop <ID> && docker rm -vf <ID> && *make* -r <service> 
#
#   -d
#
#       Optional debug ON. If specified, trigger verbose output during
#       run, especially during testing. Useful for debugging.
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
#       the 'pfcon/pman/pfioh/pfurl' services are being locally 
#       developed/debugged.
#
#       


source ./decorate.sh 

declare -i STEP=0
declare -i b_restart=0
declare -i b_pause=0
declare -i b_skipIntro=0
declare -i b_norestartinteractive_chris_dev=0
declare -i b_debug=0
declare -i b_swarmAdvertiseAdr=0
declare -i b_storeBaseOverride=0
COMPUTEENV="host"
SWARMADVERTISEADDR=""
RESTART=""
HERE=$(pwd)
echo "Starting script in dir $HERE"

CREPO=fnndsc
TAG=:latest

if [[ -f .env ]] ; then
    source .env 
fi

while getopts "r:psidUIa:S:e:" opt; do
    case $opt in
        e) COMPUTEENV=$OPTARG                   ;; 
        r) b_restart=1
           RESTART=$OPTARG                      ;;
        p) b_pause=1                            ;;
        s) b_skipIntro=1                        ;;
        i) b_norestartinteractive_chris_dev=1   ;;
        a) b_swarmAdvertiseAdr=1
            SWARMADVERTISEADDR=$OPTARG          ;;
        d) b_debug=1                            ;;
        U) b_skipUnitTests=1                    ;;
        I) b_skipIntegrationTests=1             ;;
        S) b_storeBaseOverride=1
           STOREBASE=$OPTARG                    ;;
    esac
done

shift $(($OPTIND - 1))
if (( $# == 1 )) ; then
    REPO=$1
    export CREPO=$(echo $REPO | awk -F \: '{print $1}')
    export TAG=$(echo $REPO | awk -F \: '{print $2}')
    if (( ${#TAG} )) ; then
        TAG=":$TAG"
    fi
fi

declare -a A_CONTAINER=(
    "chris:dev"
    "chris_store"
    "pfcon${TAG}"
    "pfurl${TAG}"
    "pfioh${TAG}"
    "pman${TAG}"
    "swarm"
    "pfdcm${TAG}"
    "docker-swift-onlyone"
)

title -d 1 "Setting global exports..."
    if (( ! b_storeBaseOverride )) ; then
        if [[ ! -d FS/remote ]] ; then
            mkdir -p FS/remote
        fi
        cd FS/remote
        STOREBASE=$(pwd)
        cd $HERE
    fi
    echo -e "${STEP}.1 For pman override to swarm containers, exporting\n\tSTOREBASE=$STOREBASE... "
    export STOREBASE=$STOREBASE
    if (( b_debug )) ; then
        echo -e "${STEP}.2 Setting debug quiet to OFF. Note this is noisy!"
        export CHRIS_DEBUG_QUIET=0
    fi
windowBottom

if (( b_restart )) ; then
    docker-compose -f docker-compose_dev.yml stop ${RESTART}_service && docker-compose -f docker-compose_dev.yml rm -f ${RESTART}_service
    docker-compose -f docker-compose_dev.yml run --service-ports ${RESTART}_service
else
    title -d 1 "Using <$CREPO> family containers..."
    if (( ! b_skipIntro )) ; then 
    if [[ $CREPO == "fnndsc" ]] ; then
            echo "Pulling latest version of all containers..."
            for CONTAINER in ${A_CONTAINER[@]} ; do
                echo ""
                CMD="docker pull ${CREPO}/$CONTAINER"
                echo -e "\t\t\t${White}$CMD${NC}"
                echo $sep
                echo $CMD | sh
                echo $sep
            done
        fi
    fi
    windowBottom

    if (( ! b_skipIntro )) ; then 
        title -d 1 "Will use containers with following version info:"
        for CONTAINER in ${A_CONTAINER[@]} ; do
            if [[   $CONTAINER != "chris:dev"            && \
                    $CONTAINER != "chris_store"          && \
                    $CONTAINER != "pl-pacsretrieve"      && \
                    $CONTAINER != "pl-pacsquery"         && \
                    $CONTAINER != "docker-swift-onlyone" && \
                    $CONTAINER != "swarm" ]] ; then
                CMD="docker run ${CREPO}/$CONTAINER --version"
                printf "${White}%40s\t\t" "${CREPO}/$CONTAINER"
                Ver=$(echo $CMD | sh | grep Version)
                echo -e "$Green$Ver"
            fi
        done
        # Determine the versions of pfurl *inside* pfcon/chris:dev/pl-pacs*
        CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/pfcon${TAG} --version"
        printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pfcon${TAG}"
        Ver=$(echo $CMD | sh | grep Version)
        echo -e "$Green$Ver"
        CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/chris:dev --version"
        printf "${White}%40s\t\t" "pfurl inside ${CREPO}/CUBE"
        Ver=$(echo $CMD | sh | grep Version)
        echo -e "$Green$Ver"
        # CMD="docker run --rm --entrypoint /usr/local/bin/pfurl ${CREPO}/pl-pacsquery --version"
        # printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pl-pacsquery"
        # Ver=$(echo $CMD | sh | grep Version)
        # echo -e "$Green$Ver"
        # CMD="docker run --rm --entrypoint /usr/local/bin/pfurl ${CREPO}/pl-pacsretrieve --version"
        # printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pl-pacsretrieve"
        # Ver=$(echo $CMD | sh | grep Version)
        # echo -e "$Green$Ver"
        windowBottom
    fi

    title -d 1 "Stopping and restarting the docker swarm... "
    docker swarm leave --force
    if (( b_swarmAdvertiseAdr )) ; then
        docker swarm init --advertise-addr=$SWARMADVERTISEADDR
    else
        docker swarm init --advertise-addr 127.0.0.1
    fi
    windowBottom

    title -d 1 "Shutting down any running CUBE and CUBE related containers... "
    docker-compose -f docker-compose_dev.yml stop
    docker-compose -f docker-compose_dev.yml rm -vf
    for CONTAINER in ${A_CONTAINER[@]} ; do
        printf "%30s" "$CONTAINER"
        docker ps -a                                                        |\
            grep $CONTAINER                                                 |\
            awk '{printf("docker stop %s && docker rm -vf %s\n", $1, $1);}' |\
            sh >/dev/null
        printf "${Green}%20s${NC}\n" "done"
    done
    windowBottom

    cd $HERE
    title -d 1 "Changing permissions to 755 on" " $(pwd)"
    echo "chmod -R 755 $(pwd)"
    chmod -R 755 $(pwd)
    windowBottom

    title -d 1 "Checking required FS directory tree for remote services in host filesystem..."
    mkdir -p FS/local
    mkdir -p FS/remote
    mkdir -p FS/data
    chmod -R 777 FS
    b_FSOK=1
    type -all tree >/dev/null 2>/dev/null
    if (( ! $? )) ; then
        tree FS
        report=$(tree FS | tail -n 1)
        if [[ "$report" != "3 directories, 0 files" ]] ; then 
            b_FSOK=0
        fi
    else
        report=$(find FS 2>/dev/null)
        lines=$(echo "$report" | wc -l)
        if (( lines != 4 )) ; then
            b_FSOK=0
        fi
    fi
    if (( ! b_FSOK )) ; then 
        printf "\n${Red}There should only be 3 directories and no files in the FS tree!\n"
        printf "${Yellow}Please manually clean/delete the entire FS tree and re-run.\n"
        printf "${Yellow}\nThis script will now exit with code '1'.\n\n"
        exit 1
    fi
    echo "Done."
    windowBottom

    title -d 1 "Starting CUBE containerized development environment using " " ./docker-compose_dev.yml"
    # export HOST_IP=$(ip route | grep -v docker | awk '{if(NF==11) print $9}')
    # echo "Exporting HOST_IP=$HOST_IP as environment var..."
    echo "docker-compose -f docker-compose_dev.yml up -d"
    docker-compose -f docker-compose_dev.yml up -d
    windowBottom

    title -d 1 "Pause for manual restart of services?"
    if (( b_pause )) ; then
        read -n 1 -p "Hit ANY key to continue..." anykey
        echo ""
    fi
    windowBottom

    title -d 1 "Waiting until ChRIS database server is ready to accept connections..."
    docker-compose -f docker-compose_dev.yml exec chris_dev_db sh -c 'while ! mysqladmin -uroot -prootp status 2> /dev/null; do sleep 5; done;'
    # Give all permissions to chris user in the DB. This is required for the Django tests:
    docker-compose -f docker-compose_dev.yml exec chris_dev_db mysql -uroot -prootp -e 'GRANT ALL PRIVILEGES ON *.* TO "chris"@"%"'
    windowBottom

    if (( ! b_skipUnitTests )) ; then
        title -d 1 "Running Django Unit tests..."
        docker-compose -f docker-compose_dev.yml exec chris_dev python manage.py test --exclude-tag integration
        windowBottom
    fi

    if (( ! b_skipIntegrationTests )) ; then
        title -d 1 "Running Django Integration tests..."
        docker-compose -f docker-compose_dev.yml exec chris_dev python manage.py test --tag integration
        windowBottom
    fi

    title -d 1 "Waiting until ChRIS store is ready to accept connections..."
    docker-compose -f docker-compose_dev.yml exec chrisstore sh -c 'while ! curl -sSf http://localhost:8010/api/v1/users/ 2> /dev/null; do sleep 5; done;'
    windowBottom

    title -d 1 "Creating two ChRIS STORE API users"
    echo ""
    echo "Setting superuser chris:chris1234..."
    docker-compose -f docker-compose_dev.yml exec chrisstore /bin/bash -c 'python manage.py createsuperuser --noinput --username chris --email chris@babymri.org 2> /dev/null;'
    docker-compose -f docker-compose_dev.yml exec chrisstore /bin/bash -c \
    'python manage.py shell -c "from django.contrib.auth.models import User; user = User.objects.get(username=\"chris\"); user.set_password(\"chris1234\"); user.save()"'
    echo ""
    echo "Setting normal user cubeadmin:cubeadmin1234..."
    docker-compose -f docker-compose_dev.yml exec chrisstore /bin/bash -c 'python manage.py createsuperuser --noinput --username cubeadmin --email cubeadmin@babymri.org 2> /dev/null;'
    docker-compose -f docker-compose_dev.yml exec chrisstore /bin/bash -c \
    'python manage.py shell -c "from django.contrib.auth.models import User; user = User.objects.get(username=\"cubeadmin\"); user.set_password(\"cubeadmin1234\"); user.save()"'
    echo ""
    docker-compose -f docker-compose_dev.yml restart chrisstore
    echo ""
    windowBottom

    #
    # Plugin array list for list of plugin names to be registered in the dev
    # syste
    #
    # If the main module name within a plugin is different than the plugin name,
    # separate the plugin and module strings with a '/' characater (see below).
    #
    # Indicate a specific remote compute environment with a [:<env>] 
    # specification.
    #
    declare -a plugins=( 
                         "simplefsapp"
                         "simplefsapp_moc:moc"
                         "simpledsapp"
                         "simpledsapp_moc:moc"
                         "s3retrieve"
                         "s3push"
                         "dircopy"
                         "pfdicom_tagextract/dcm_tagExtract"
                         "pfdicom_tagsub/dcm_tagSub"
                         "pacscopy"
                         "mpcs"
                         "freesurfer_pp"
                         "z2labelmap"
                         "mri10yr06mo01da_normal"
                         "mpcs_moc:moc"
                         "freesurfer_pp_moc:moc"
                         "z2labelmap_moc:moc"
                         "mri10yr06mo01da_normal_moc:moc"
    )

    title -d 1 "Checking on container plugins..."
        if [[ $CREPO == "fnndsc" ]] ; then
            echo "Pulling latest version of all fnndsc plugin containers..."
            for plugin in "${plugins[@]}" ; do
                printf "${Cyan}%-25s${NC} <--- ${LightBlue}[ dockerhub ]${NC}: " "[ $plugin ]"                
                dockerhubRepo=$(echo $plugin        | awk -F\/ '{print $1}')
                dockerhubRepo=$(echo $dockerhubRepo | awk -F\: '{print $1}')
                moduleName=$(echo $plugin           | awk -F\/ '{print $2}')
                if (( ! ${#moduleName} )) ; then
                    moduleName=$dockerhubRepo
                fi
                PLUGIN_DOCK="fnndsc/pl-${dockerhubRepo}"
                CMD="docker pull $PLUGIN_DOCK"
                echo -e "${White}$CMD${NC}"
                echo $sep
                echo $CMD | sh
                echo $sep
            done
        fi
    windowBottom

    title -d 1 "Automatically uploading some plugins to the ChRIS store..."
    declare -i i=1
    for plugin in "${plugins[@]}"; do
        dockerhubRepo=$(echo $plugin        | awk -F\/ '{print $1}')
        dockerhubRepo=$(echo $dockerhubRepo | awk -F\: '{print $1}')
        moduleName=$(echo $plugin           | awk -F\/ '{print $2}')
        if (( ! ${#moduleName} )) ; then
            moduleName=$dockerhubRepo
        fi
        printf "%8s" "${STEP}.$i: "
        printf "${Cyan}%-28s${NC} ---> ${LightBlue}[ ChRIS store ]${NC}... " "[ $dockerhubRepo ]"
        PLUGIN_DOCK="fnndsc/pl-${dockerhubRepo}"
        PLUGIN_REP=$(docker run --rm "$PLUGIN_DOCK" "${moduleName}.py" --json 2> /dev/null;)
        docker-compose -f docker-compose_dev.yml exec chrisstore python plugins/services/manager.py add "${dockerhubRepo}" cubeadmin https://github.com/FNNDSC "$PLUGIN_DOCK" --descriptorstring "$PLUGIN_REP"
        printf "\t${LightGreen}[ success ]${NC}\n"
        ((i++))
    done
    windowBottom

    title -d 1 "Automatically creating two unlocked pipelines in the ChRIS STORE" "(unmutable and available to all users)"
    S3_PLUGIN_VER=$(docker run --rm fnndsc/pl-s3retrieve s3retrieve.py --version)
    SIMPLEDS_PLUGIN_VER=$(docker run --rm fnndsc/pl-simpledsapp simpledsapp.py --version)

    PIPELINE_NAME="s3retrieve_v${S3_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}"
    echo "Creating pipeline named '$PIPELINE_NAME'"
    STR1='[{"plugin_name": "s3retrieve", "plugin_version": "'
    STR2='", "plugin_parameter_defaults": [{"name": "bucket", "default": "somebucket"}, {"name": "awssecretkey", "default": "somekey"},
    {"name": "awskeyid", "default": "somekeyid"}], "previous_index": null}, {"plugin_name": "simpledsapp", "plugin_version": "'
    STR3='", "previous_index": 0}]'
    PLUGIN_TREE=${STR1}${S3_PLUGIN_VER}${STR2}${SIMPLEDS_PLUGIN_VER}${STR3}

    docker-compose -f docker-compose_dev.yml exec chrisstore python pipelines/services/manager.py add "${PIPELINE_NAME}" cubeadmin "${PLUGIN_TREE}" --unlock

    PIPELINE_NAME="simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}"
    echo "Creating pipeline named '$PIPELINE_NAME'"
    STR4='[{"plugin_name": "simpledsapp", "plugin_version": "'
    STR5='", "previous_index": null},{"plugin_name": "simpledsapp", "plugin_version": "'
    STR6='", "previous_index": 0},{"plugin_name": "simpledsapp", "plugin_version": "'
    STR7='", "previous_index": 0}]'
    PLUGIN_TREE=${STR4}${SIMPLEDS_PLUGIN_VER}${STR5}${SIMPLEDS_PLUGIN_VER}${STR6}${SIMPLEDS_PLUGIN_VER}${STR7}

    docker-compose -f docker-compose_dev.yml exec chrisstore python pipelines/services/manager.py add "${PIPELINE_NAME}" cubeadmin "${PLUGIN_TREE}" --unlock
    windowBottom

    title -d 1 "Automatically registering some plugins from the ChRIS store into CUBE..."
    declare -i i=1
    for plugin in "${plugins[@]}"; do
        dockerhubRepo=$(echo $plugin        | awk -F\/ '{print $1}')
        remoteCompute=$(echo $dockerhubRepo | awk -F\: '{print $2}')
        dockerhubRepo=$(echo $dockerhubRepo | awk -F\: '{print $1}')
        if (( ${#remoteCompute} )) ; then
            computeEnv=$remoteCompute
        else
            computeEnv=$COMPUTEENV            ``
        fi
        printf "%8s" "${STEP}.$i: "
        printf "${LightBlue}[ ChRIS store ]${NC}::${Cyan}%-28s${NC} --> ${Yellow}[ CUBE ]${NC}::${Cyan}$computeEnv${NC}..." "[ $dockerhubRepo ]"
        docker-compose -f docker-compose_dev.yml exec chris_dev python plugins/services/manager.py add "${dockerhubRepo}" $computeEnv http://chrisstore:8010/api/v1/
        printf "\t${LightGreen}[ success ]${NC}\n"
        ((i++))
    done
    windowBottom

    title -d 1 "Creating two ChRIS API users"
    echo ""
    echo "Setting superuser chris:chris1234..."
    docker-compose -f docker-compose_dev.yml exec chris_dev /bin/bash -c 'python manage.py createsuperuser --noinput --username chris --email dev@babymri.org 2> /dev/null;'
    docker-compose -f docker-compose_dev.yml exec chris_dev /bin/bash -c \
    'python manage.py shell -c "from django.contrib.auth.models import User; user = User.objects.get(username=\"chris\"); user.set_password(\"chris1234\"); user.save()"'
    echo ""
    echo "Setting normal user cube:cube1234..."
    docker-compose -f docker-compose_dev.yml exec chris_dev /bin/bash -c 'python manage.py createsuperuser --noinput --username cube --email dev@babymri.org 2> /dev/null;'
    docker-compose -f docker-compose_dev.yml exec chris_dev /bin/bash -c \
    'python manage.py shell -c "from django.contrib.auth.models import User; user = User.objects.get(username=\"cube\"); user.set_password(\"cube1234\"); user.save()"'
    echo ""
    windowBottom

    title -d 1 "Automatically creating a locked pipeline in CUBE" "(mutable by the owner and not available to other users)"
    PIPELINE_NAME="s3retrieve_v${S3_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}_1"
    echo "Creating pipeline named '$PIPELINE_NAME'"
    PLUGIN_TREE=${STR1}${S3_PLUGIN_VER}${STR2}${SIMPLEDS_PLUGIN_VER}${STR3}

    docker-compose -f docker-compose_dev.yml exec chris_dev python pipelines/services/manager.py add "${PIPELINE_NAME}" cube "${PLUGIN_TREE}"
    windowBottom

    title -d 1 "Automatically creating an unlocked pipeline in CUBE" "(unmutable and available to all users)"
    PIPELINE_NAME="simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}-simpledsapp_v${SIMPLEDS_PLUGIN_VER}"
    echo "Creating pipeline named '$PIPELINE_NAME'"
    PLUGIN_TREE=${STR4}${SIMPLEDS_PLUGIN_VER}${STR5}${SIMPLEDS_PLUGIN_VER}${STR6}${SIMPLEDS_PLUGIN_VER}${STR7}

    docker-compose -f docker-compose_dev.yml exec chris_dev python pipelines/services/manager.py add "${PIPELINE_NAME}" cube "${PLUGIN_TREE}" --unlock
    windowBottom

    if (( !  b_norestartinteractive_chris_dev )) ; then
        title -d 1 "Restarting CUBE's Django development server" "in interactive mode..."
        docker-compose -f docker-compose_dev.yml stop chris_dev
        docker-compose -f docker-compose_dev.yml rm -f chris_dev
        docker-compose -f docker-compose_dev.yml run --service-ports chris_dev
        echo ""
        windowBottom
    else
        title -d 1 "Restarting CUBE's Django development server" "in non-interactive mode..."
        docker-compose -f docker-compose_dev.yml restart chris_dev
        echo ""
        windowBottom
    fi
fi
