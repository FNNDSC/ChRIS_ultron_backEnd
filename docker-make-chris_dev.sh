#!/bin/bash
#
# NAME
#
#   docker-make-chris_dev.sh
#
# SYNPOSIS
#
#   docker-make-chris_dev.sh [local|fnndsc]
#
# DESC
# 
#   'dockeer-make-chris_dev.sh' is the main entry point for instantiating a 
#   complete backend dev environment.
#
#   It creates a pattern of directories and symbolic links that reflect the
#   declarative environment of the docker-compose.yml contents.
#
# ARGS
#
#   [local|fnndsc] (optional, default = 'fnndsc')
#
#       If specified, denotes the container "family" to use. 
#
#       The 'fnndsc' family are the containers as hosted on docker hub. 
#       Using 'fnndsc' will always attempt to pull the latest container first.
#
#       The 'local' family are containers that are assumed built on the local
#       machine and assumed to exist. The 'local' containers are used when
#       the 'pfcon/pman/pfioh/pfurl' services are being locally 
#       developed/debugged.
#

   ESC(){ echo -en "\033";}                            # escape character
 CLEAR(){ echo -en "\033c";}                           # the same as 'tput clear'
 CIVIS(){ echo -en "\033[?25l";}                       # the same as 'tput civis'
 CNORM(){ echo -en "\033[?12l\033[?25h";}              # the same as 'tput cnorm'
  TPUT(){ echo -en "\033[${1};${2}H";}                 # the same as 'tput cup'
COLPUT(){ echo -en "\033[${1}G";}                      # put text in the same line as the specified column
  MARK(){ echo -en "\033[7m";}                         # the same as 'tput smso'
UNMARK(){ echo -en "\033[27m";}                        # the same as 'tput rmso'
  DRAW(){ echo -en "\033%";echo -en "\033(0";}        # switch to 'garbage' mode
 WRITE(){ echo -en "\033(B";}                          # return to normal mode from 'garbage' on the screen
  BLUE(){ echo -en "\033c\033[0;1m\033[37;44m\033[J";} # reset screen, set background to blue and font to white

# Foreground
RED='\033[0;31m'
NC='\033[m' # No Color
Black='\033[0;30m'     
DarkGray='\033[1;30m'
Red='\033[0;31m'     
LightRed='\033[1;31m'
Green='\033[0;32m'     
LightGreen='\033[1;32m'
Brown='\033[0;33m'     
Yellow='\033[1;33m'
Blue='\033[0;34m'     
LightBlue='\033[1;34m'
Purple='\033[0;35m'     
LightPurple='\033[1;35m'
Cyan='\033[0;36m'     
LightCyan='\033[1;36m'
LightGray='\033[0;37m'     
White='\033[1;37m'

# Background
NC='\033[m' # No Color
BlackBG='\033[0;40m'     
DarkGrayBG='\033[1;40m'
RedBG='\033[0;41m'     
LightRedBG='\033[1;41m'
GreenBG='\033[0;42m'     
LightGreenBG='\033[1;42m'
BrownBG='\033[0;43m'     
YellowBG='\033[1;43m'
BlueBG='\033[0;44m'     
LightBlueBG='\033[1;44m'
PurpleBG='\033[0;45m'     
LightPurpleBG='\033[1;45m'
CyanBG='\033[0;46m'     
LightCyanBG='\033[1;46m'
LightGrayBG='\033[0;47m'     
WhiteBG='\033[1;47m'


declare -i STEP=0
declare -i b_restart=0
RESTART=""
HERE=$(pwd)
echo "Starting script in dir $HERE"
CREPO=fnndsc

declare -a A_CONTAINER=(
    "chris_dev_backend"
    "pfcon:dev"
    "pfurl:dev"
    "pfioh:dev"
    "pman:dev"
    "swarm"
    "pfdcm:dev"
    "pl-pacsquery"
    "pl-pacsretrieve"
)

function title {
    declare -i b_date=0
    local OPTIND
    while getopts "d:" opt; do
        case $opt in 
            d) b_date=$OPTARG ;;
        esac
    done
    shift $(($OPTIND - 1))

    STEP=$(expr $STEP + 1 )
    MSG="$1"
    MSG2="$2"
    TITLE=$(echo " $STEP.0: $MSG ")
    LEN=$(echo "$TITLE" | awk -F\| {'printf("%s", length($1));'})
    if ! (( LEN % 2 )) ; then
        TITLE="$TITLE "
    fi
    MSG=$(echo -e "$TITLE" | awk -F\| {'printf("%*s%*s\n", 39+length($1)/2, $1, 40-length($1)/2, "");'})
    if (( ${#MSG2} )) ; then
        TITLE2=$(echo " $MSG2 ")
        LEN2=$(echo "$TITLE2" | awk -F\| {'printf("%s", length($1));'})
        MSG2=$(echo -e "$TITLE2" | awk -F\| {'printf("%*s%*s\n", 39+length($1)/2, $1, 40-length($1)/2, "");'})
    fi
    printf "\n"
    DATE=$(date)
    DRAW
    if (( b_date )) ; then
        printf "${LightBlue}lqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqk\nx"
        WRITE
        printf "%-30s" "$DATE"
        DRAW 
        printf "x\n"
        printf "${Yellow}tqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqvqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqk\n"
    else
        printf "${Yellow}lqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqk\n"
    fi
    printf "x"
    WRITE
    printf "${LightPurple}$MSG${Yellow}"
    if (( ${#MSG2} )) ; then
        DRAW
        printf "x\nx"
        WRITE
        printf "${LightPurple}$MSG2${Yellow}"
    fi
    DRAW
    printf "x\n"
    printf "${Yellow}tqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqu\n"
    WRITE
    printf "${NC}"
}

function windowBottom {
    # printf "a b c d f e f g h i j k l m n o p q r s t u v w x y z]\n"
    DRAW
    # printf "a b c d f e f g h i j k l m n o p q r s t u v w x y z]\n"
    printf "${Yellow}"
    printf "mwqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqv${Brown}qk\n"
    # printf "mqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqj\n"
    printf "${Brown}"
    printf " mqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqj\n"
    WRITE
    printf "${NC}"
}

while getopts "r:" opt; do
    case $opt in 
        r) b_restart=1
           RESTART=$OPTARG  ;;
    esac
done
shift $(($OPTIND - 1))
if (( $# == 1 )) ; then
    CREPO=$1
fi
export CREPO=$CREPO

title -d 1 "Using <$CREPO> containers..."
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
windowBottom

if (( b_restart )) ; then
    docker-compose stop ${RESTART}_service && docker-compose rm -f ${RESTART}_service
    docker-compose run --service-ports ${RESTART}_service
else
    title -d 1 "Will use containers with following version info:"
    for CONTAINER in ${A_CONTAINER[@]} ; do
        if [[   $CONTAINER != "chris_dev_backend"   && \
                $CONTAINER != "pl-pacsretrieve"     && \
                $CONTAINER != "pl-pacsquery"        && \
                $CONTAINER != "swarm" ]] ; then
            CMD="docker run ${CREPO}/$CONTAINER --version"
            printf "${White}%40s\t\t" "${CREPO}/$CONTAINER"
            Ver=$(echo $CMD | sh | grep Version)
            echo -e "$Green$Ver"
        fi
    done
    # And for the version of pfurl *inside* pfcon!
    CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/pfcon --version"
    printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pfcon"
    Ver=$(echo $CMD | sh | grep Version)
    echo -e "$Green$Ver"
    CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/chris_dev_backend --version"
    printf "${White}%40s\t\t" "pfurl inside ${CREPO}/CUBE"
    Ver=$(echo $CMD | sh | grep Version)
    echo -e "$Green$Ver"
    CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/pl-pacsquery --version"
    printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pl-pacsquery"
    Ver=$(echo $CMD | sh | grep Version)
    echo -e "$Green$Ver"
    CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/pl-pacsretrieve --version"
    printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pl-pacsretrieve"
    Ver=$(echo $CMD | sh | grep Version)
    echo -e "$Green$Ver"
    windowBottom

    title -d 1 "Stopping and restarting the docker swarm... "
    docker swarm leave --force
    docker swarm init
    windowBottom

    title -d 1 "Shutting down any running CUBE and CUBE related containers... "
    docker-compose stop
    docker-compose rm -vf
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

    title -d 1 "Creating tmp dirs for volume mounting into containers..."
    echo "${STEP}.1: Remove tree root 'FS'.."
    rm -fr ./FS 
    echo "${STEP}.2: Create tree structure for remote services in host filesystem..."
    mkdir -p FS/local
    chmod 777 FS/local
    mkdir -p FS/remote
    chmod 777 FS/remote
    # mkdir -p FS/users
    # chmod 777 FS/users
    chmod 777 FS
    cd FS/remote
    echo -e "${STEP}.3 For pman override to swarm containers, exporting\n\tSTOREBASE=$(pwd)... "
    export STOREBASE=$(pwd)
    # chmod 777 FS/users
    # echo "1.3: Create tree structure to emulate volume mapping"
    # echo "1.3: This allows for easy switching/running between"
    # echo "1.3: containerized and non-containerized environments."
    # sudo rm -fr /hostFS 2>/dev/null
    # sudo mkdir -p /hostFS
    # cd /hostFS
    # sudo ln -s ${HERE}/FS/local   pfconFS
    # sudo ln -s ${HERE}/FS/remote  storeBase
    cd $HERE
    windowBottom

    title -d 1 "Starting CUBE containerized development environment using " " ./docker-compose.yml"
    # export HOST_IP=$(ip route | grep -v docker | awk '{if(NF==11) print $9}')
    # echo "Exporting HOST_IP=$HOST_IP as environment var..."
    echo "docker-compose up -d"
    docker-compose up -d
    windowBottom

    title -d 1 "Waiting until mysql server is ready to accept connections..."
    docker-compose exec chris_dev_db sh -c 'while ! mysqladmin -uroot -prootp status 2> /dev/null; do sleep 5; done;'
    # Give all permissions to chris user in the DB. This is required for the Django tests:
    docker-compose exec chris_dev_db mysql -uroot -prootp -e 'GRANT ALL PRIVILEGES ON *.* TO "chris"@"%"'
    windowBottom

    title -d 1 "Making migrations..."
    docker-compose exec chris_dev python manage.py migrate
    windowBottom

    title -d 1 "Registering plugins..."
    # Declare an array variable for the list of plugin dock images
    # Add a new plugin image name to the list if you want it to be automatically registered
    docker-compose exec chris_dev /bin/bash -c \
    'declare -a plugins=("fnndsc/pl-simplefsapp"
                        "fnndsc/pl-simpledsapp"
                        "fnndsc/pl-pacsquery"
                        "fnndsc/pl-pacsretrieve"
                        "fnndsc/pl-med2img"
                        "fnndsc/pl-s3retrieve"
                        "fnndsc/pl-s3push"
                        "fnndsc/pl-dircopy"
                        "local/pl-geretrieve"
                        "local/pl-gepush"
                        )
    declare -i i=1
    declare -i STEP=10
    for plugin in "${plugins[@]}"; do 
        echo "${STEP}.$i: Registering $plugin..."
        python3 plugins/services/manager.py --add ${plugin} 2> /dev/null; 
        ((i++))
    done'
    windowBottom

    title -d 1 "Running Django tests..."
    docker-compose exec chris_dev python manage.py test
    windowBottom

    title -d 1 "Restarting Django development server..."
    docker-compose restart chris_dev
    windowBottom

    title -d 1 "ChRIS API user creation"
    echo 'Now create two users. Please name one of the users "chris"'
    echo ""
    docker-compose exec chris_dev python manage.py createsuperuser
    docker-compose exec chris_dev python manage.py createsuperuser
    windowBottom

    title -d 1 "Restarting Django development server in interactive mode..."
    docker-compose stop chris_dev
    docker-compose rm -f chris_dev
    docker-compose run --service-ports chris_dev
    echo ""
    windowBottom
fi
