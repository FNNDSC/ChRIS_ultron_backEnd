#!/bin/bash
#
# NAME
#
#   user_add.sh
#
# SYNPOSIS
#
#   user_add.sh   [-t dev|deploy]                                       \
#                 [-s <step>] [-U]                                      \
#                 [-S]                                                  \
#                 <commaSeparatedListOfUsers@passwords>
#
# DESC
#
#   'user_add.sh' adds new users to an existing and instantiated
#   CUBE or ChRIS Store.
#
# Notes on user list
#
# The user list is a comma separated list, each element conforming to a
# <user>:<password>:<email> tuple, i.e:
#
#       'john:john1234:john@someplace.com,harry:!!@#fds:harry@gmail.com'
#
# To protect text from being interpreted by the shell, quote the list in
# single quotes. Due to the parsing of this string, it does mean that
# passwords cannot contain ':' or ',' characters.
#
##
# ARGS
#
#   [-t dev|deploy]
#
#       Choose either 'dev' or 'deploy' targets. This affects the choice of
#       underlying docker-compose yaml to process as well as the name of the
#       chris service.
#
#       Default is 'dev'.
#
#   [-s <step>]
#
#       Start STEP counter at <step>. This is useful for cases when
#       this script is called from another staged script and contintuity
#       requires a <step> offset.
#
#   [-U]
#
#       If specified, create this (these) user(s) as superusers.
#
#   [-S]
#
#       If specified, add user to the ChRIS Store, otherwise add user to 
#       CUBE.
#

source ./decorate.sh
source ./cparse.sh

declare -a a_USERPASS=()
DOCKER_COMPOSE_FILE=docker-compose_dev.yml
CHRIS=chris_dev
STORE=chris_store
TARGET=dev
declare -i STEP=0
declare -i b_superUser=0
declare -i b_CUBE=1
HERE=$(pwd)
LINE="------------------------------------------------"

if [[ -f .env ]] ; then
    source .env
fi

while getopts "f:s:US" opt; do
    case $opt in
        s)  STEP=$OPTARG
            STEP=$(( STEP -1 ))                 ;;
        t)  TARGET=$OPTARG                      ;;
        U)  b_superUser=1                       ;;
        S)  b_CUBE=0                            ;;
    esac
done

case $TARGET in
    dev)    DOCKER_COMPOSE_FILE=docker-compose_dev.yml
            CHRIS=chris_dev
            STORE=chris_store
            ;;
    deploy) DOCKER_COMPOSE_FILE=docker-compose.yml
            CHRIS=chris
            STORE=chris_store
            ;;
    *)      DOCKER_COMPOSE_FILE=docker-compose_dev.yml
            CHRIS=chris_dev
            STORE=chris_store
            ;;
esac

shift $(($OPTIND - 1))
L_USERPASS=$*
IFS=',' read -ra a_USERPASS <<< "$L_USERPASS"

if (( b_CUBE )) ; then
    CHRIS=$CHRIS
    title -d 1 "Creating ChRIS API / CUBE users..."
else
    CHRIS=$STORE
    title -d 1 "Creating ChRIS Store users..."
fi
    declare -i i=1
    declare -i b_createSuccess=0
    declare -i b_createFail=0
    echo ""                                                         | ./boxes.sh
    echo ""                                                         | ./boxes.sh
    for userpass in "${a_USERPASS[@]}" ; do
        echo -en "\033[2A\033[2K"
        a_userpass=()
        IFS=':' read -ra a_userpass <<< "$userpass"
        boxcenter "Specified user..."  ${LightPurple}
        username="$(echo -e "${a_userpass[0]}" | tr -d '[:space:]')"
        password="$(echo -e "${a_userpass[1]}" | tr -d '[:space:]')"
        email="$(echo -e "${a_userpass[2]}" | tr -d '[:space:]')"
        tcprint "Yellow" "user: "       "LightCyan"     "$username"     40 -40
        tcprint "Yellow" "password: "   "LightCyan"     "$password"     40 -40
        tcprint "Yellow" "email: "      "LightCyan"     "$email"        40 -40
        if (( b_superUser )) ; then
            echo "" | ./boxes.sh
            accountType="Super  user account creation "
            printf "${Yellow}%5s${LightCyan}%-32s${Yellow}%28s${blink}${LightGreen}%14s${NC}\n"       \
            "$i: " "$username" "$accountType" "[ superuser  ]"   | ./boxes.sh
            windowBottom
            docker-compose -f ${DOCKER_COMPOSE_FILE}                        \
                exec ${CHRIS} /bin/bash -c                                  \
                "python manage.py createsuperuser --noinput                 \
                        --username $username                                \
                        --email $email 2> /dev/null;" >& dc.out >/dev/null
            status=$?
            echo -en "\033[3A\033[2K"
            cat dc.out | ./boxes.sh
            CMD='python manage.py shell -c                                  \
                    "from django.contrib.auth.models import User;           \
                    user=User.objects.get(username=\"'$username'\");        \
                    user.set_password(\"'$password'\");                     \
                    user.save()"'
            printf "${Yellow}%5s${LightCyan}%-32s${Yellow}%28s${blink}${LightGreen}%14s${NC}\n"       \
            "$i: " "$username" "$accountType" "[   adding   ]"   | ./boxes.sh
            windowBottom
            docker-compose -f ${DOCKER_COMPOSE_FILE}                        \
                exec ${CHRIS} /bin/bash -c                                  \
                "$CMD" >& dc.out >/dev/null
            status=$?
            echo -en "\033[3A\033[2K"
            cat dc.out | ./boxes.sh
        else
            echo "" | ./boxes.sh
            accountType="Normal user account creation "
            CMD='python manage.py shell -c                                  \
                    "from users.serializers import UserSerializer;          \
                    us=UserSerializer(data={\"username\":\"'$username'\",   \
                                            \"password\":\"'$password'\",   \
                                            \"email\":\"'$email'\"});       \
                    us.is_valid();                                          \
                    us.save()"'
            printf "${Yellow}%5s${LightCyan}%-32s${Yellow}%28s${blink}${LightGreen}%14s${NC}\n"       \
            "$i: " "$username" "$accountType" "[ generating ]"  | ./boxes.sh
            windowBottom
            docker-compose -f ${DOCKER_COMPOSE_FILE}                        \
                exec ${CHRIS} /bin/bash -c                                  \
                "$CMD" >& dc.out >/dev/null
            status=$?
            echo -en "\033[3A\033[2K"
            cat dc.out | ./boxes.sh
        fi
        if (( status == 0 )) ; then
            printf "${Yellow}%5s${LightCyan}%-32s${Yellow}%28s${LightGreenBG}${White}%14s${NC}\n"       \
            "$i: " "$username" "$accountType" "[ successful ]"            | ./boxes.sh
            b_createSuccess=$(( b_createSuccess+=1 ))
        else
            printf "${Yellow}%5s${LightCyan}%-32s${Yellow}%28s${RedBG}${White}%14s${NC}\n"       \
            "$i: " "$username" "$accountType" "[   error    ]"            | ./boxes.sh
            b_createFail=$(( b_createFail+=1 ))
        fi
        echo ""                                                           | ./boxes.sh
        ((i++))
        windowBottom
    done
    echo -en "\033[2A\033[2K"
    echo ""                                                             | ./boxes.sh
    if (( b_createSuccess > 0 )) ; then
        printf "${LightCyan}%16s${LightGreen}%-64s${NC}\n"              \
            "$b_createSuccess"                                          \
            " user login(s) successfully created in CUBE"               | ./boxes.sh
        echo ""                                                         | ./boxes.sh
    fi
    if (( b_createFail > 0 )) ; then
        printf "${LightRed}%16s${Brown}%-64s${NC}\n"                    \
            "$b_createFail"                                             \
        " user login(s) were not successfully created."                 | ./boxes.sh
        boxcenter "an unsuccessful user account creation is usually  "  ${LightPurple}
        boxcenter "because either the  username  and/or user  email  "  ${LightPurple}
        boxcenter "already exists in CUBE. Please  verify  that the  "  ${LightPurple}
        boxcenter "username and email are unique.                    "  ${LightPurple}
        echo ""                                                         | ./boxes.sh
    fi
windowBottom
