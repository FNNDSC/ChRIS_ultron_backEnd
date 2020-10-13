#!/bin/bash
#
# NAME
#
#   plugin_add.sh
#
# SYNPOSIS
#
#   plugin_add.sh [-s <step>] [-j] <commaSeparatedListOfPluginSpecsToAdd>
#
# DESC
#
#   'plugin_add.sh' adds new plugins to an existing and instantiated
#   CUBE.
#
# Notes on pluginList
#
# The plugin list is a comma separated list, each element conforming to a
# cparse specification, i.e:
#
#               fnndsc/pl-pfdicom_tagextract::dcm_tagExtract^moc
#
#               [<repo>/]<container>[::<mainModuleName>[^<env>]]
#
##
# ARGS
#
#   [-s <step>]
#
#       Start STEP counter at <step>. This is useful for cases when
#       this script is called from another staged script and contintuity
#       requires a <step> offset.
#
#   [-j]
#
#       Show JSON representation. If specified, also "print" a given plugin
#       JSON representation during the store registration phase.
#

source ./decorate.sh
source ./cparse.sh

declare -i STEP=0
declare -i b_json=0
HERE=$(pwd)
LINE="------------------------------------------------"

if [[ -f .env ]] ; then
    source .env
fi

while getopts "s:j" opt; do
    case $opt in
        s)  STEP=$OPTARG
            STEP=$(( STEP -1 ))                 ;;
        j)  b_json=1                            ;;
    esac
done

declare -a a_PLUGINRepoEnv=()
declare -a a_storePluginUser=()
declare -a a_storePluginOK=()

shift $(($OPTIND - 1))
L_PLUGINS=$*
IFS=',' read -ra a_PLUGINRepoEnv <<< "$L_PLUGINS"

title -d 1 "Creating array of <REPO>/<CONTAINER> from plugin list..."
    for plugin in "${a_PLUGINRepoEnv[@]}" ; do
        cparse $plugin ".py" "REPO" "CONTAINER" "MMN" "ENV"
        tcprint Yellow "Processing env [$ENV] for " LightCyan "$REPO/$CONTAINER" "40" "-40"
        a_storePluginUser+=("$REPO/$CONTAINER")
    done
    a_storePluginUser=($(printf "%s\n" "${a_storePluginUser[@]}" | sort -u | tr '\n' ' '))
windowBottom

title -d 1 "Removing any duplicate <REPO>/<CONTAINER> from plugin list..."
    a_storePluginUser=($(printf "%s\n" "${a_storePluginUser[@]}" | sort -u | tr '\n' ' '))
    numElements=${#a_storePluginUser[@]}
    tcprint "Blink;Yellow" "Unique hits " LightCyan "$numElements" "40" "-40"
    for plugin in "${a_storePluginUser[@]}" ; do
        tcprint Yellow "Image " LightCyan $plugin "40" "-40"
    done
windowBottom

title -d 1  "Checking on container plugins " \
            "and pulling latest versions where needed..."
    for plugin in "${a_storePluginUser[@]}" ; do
        cparse $plugin ".py" "REPO" "CONTAINER" "MMN" "ENV"
        if [[ $REPO == "fnndsc" ]] ; then
            printf "${LightBlueBG}${White}[ dockerhub ]${NC}::${LightCyan}%-35s${Yellow}%19s${blink}${LightGreen}%-11s${NC}\n" \
                "$REPO/$CONTAINER" "latest<--" "[ pulling ]"                        | ./boxes.sh
            windowBottom
            CMD="docker pull $REPO/$CONTAINER"
            echo $CMD | sh >& dc.out >/dev/null
            status=$?
            if (( status == 0 )) ; then
                report="[ success ]"
                reportColor=LightGreen
                a_storePluginOK+=("$plugin")
                echo -en "\033[3A\033[2K"
                printf "${LightBlueBG}${White}[ dockerhub ]${NC}::${LightCyan}%-35s${Yellow}%19s${LightGreenBG}${White}%-11s${NC}\n"     \
                "$REPO/$CONTAINER" "latest<--" "$report"                            | ./boxes.sh
            else
                report="[ failed  ]"
                reportColor=LightRed
                echo -en "\033[3A\033[2K"
                printf "${LightBlueBG}${White}[ dockerhub ]${NC}::${LightCyan}%-35s${Yellow}%19s${RedBG}${White}%-11s${NC}\n"\
                "$REPO/$CONTAINER" "latest<--" "$report"                            | ./boxes.sh
            fi
            cat dc.out | sed 's/[[:alnum:]]+:/\n&/g' | sed -E 's/(.{80})/\1\n/g'    | ./boxes.sh
        fi
    done
windowBottom

title -d 1 "Uploading plugin representations to the ChRIS store..."
    declare -i i=1
    declare -i b_uploadSuccess=0
    declare -i b_already=0
    declare -i b_uploadFail=0
    echo ""                                                         | ./boxes.sh
    echo ""                                                         | ./boxes.sh
    for plugin in "${a_PLUGINRepoEnv[@]}"; do
        echo -en "\033[2A\033[2K"
        cparse $plugin ".py" "REPO" "CONTAINER" "MMN" "ENV"
        CMD="docker run --rm $REPO/$CONTAINER ${MMN} --json 2> /dev/null"

        printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%28s${blink}${LightGreen}%12s${NC}\n"       \
        "$i: " "$REPO/$CONTAINER" "JSON representation<--" "[ getting  ]"           | ./boxes.sh
        windowBottom
        PLUGIN_REP=$(docker run --rm $REPO/$CONTAINER ${MMN} --json 2>/dev/null)
        echo -en "\033[3A\033[2K"
        if (( b_json )) ; then
            echo "$PLUGIN_REP" | python -m json.tool                                |\
                sed 's/[[:alnum:]]+:/\n&/g' | sed -E 's/(.{80})/\1\n/g'             | ./boxes.sh ${LightGreen}
        fi
        printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%28s${LightGreen}%12s${NC}\n"               \
        "$i: " "$REPO/$CONTAINER" "JSON representation<--" "[ acquired ]"           | ./boxes.sh
        windowBottom
        echo -en "\033[3A\033[2K"
        printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%28s${blink}${LightGreen}%12s${NC}\n"       \
        "$i: " "$REPO/$CONTAINER" "JSON representation<--" "[ pushing  ]"           | ./boxes.sh

        windowBottom
        docker-compose -f docker-compose_dev.yml                                    \
            exec chris_store python plugins/services/manager.py add "$CONTAINER"    \
            cubeadmin https://github.com/FNNDSC "$REPO/$CONTAINER"                  \
            --descriptorstring "$PLUGIN_REP" >& dc.out >/dev/null
        status=$?
        echo -en "\033[3A\033[2K"
        # cat dc.out | sed 's/[[:alnum:]]+:/\n&/g' | sed -E 's/(.{80})/\1\n/g'    | ./boxes.sh

        if (( status == 0 )) ; then
            printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%28s${LightGreenBG}${White}%12s${NC}\n"               \
            "$i: " "$REPO/$CONTAINER" "JSON in ChRIS store<--" "[ success  ]"  | ./boxes.sh
            b_uploadSuccess=$(( b_uploadSuccess+=1 ))
        elif (( status == 1 )) ; then
            printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%28s${PurpleBG}${White}%12s${NC}\n"            \
            "$i: " "$REPO/$CONTAINER" "JSON in ChRIS store<--" "[ already  ]"  | ./boxes.sh
            b_already=$(( b_already+=1 ))
        elif (( status == 2 )) ; then
            printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%28s${RedBG}${White}%12s${NC}\n"            \
            "$i: " "$REPO/$CONTAINER" "JSON in ChRIS store<--" "[  error   ]"  | ./boxes.sh
            b_uploadFail=$(( b_uploadFail+=1 ))
        fi
        ((i++))
        windowBottom
    done
    echo -en "\033[2A\033[2K"
    echo ""                                                             | ./boxes.sh
    if (( b_uploadSuccess > 0 )) ; then
        printf "${LightCyan}%16s${LightGreen}%-64s${NC}\n"              \
            "$b_uploadSuccess"                                          \
            " representation(s) successfully uploaded to ChRIS Store"   | ./boxes.sh
        echo ""                                                         | ./boxes.sh
    fi
    if (( b_already > 0 )) ; then
        printf "${LightCyan}%16s${Yellow}%-64s${NC}\n"                  \
            "$b_already"                                                \
            " representation(s) were already in the ChRIS Store"        | ./boxes.sh
        boxcenter "An 'already' state simply means the representation"  ${LightPurple}
        boxcenter "is already in the ChRIS Store --  most  likely due"  ${LightPurple}
        boxcenter "a prior attempt at registration.  Also, note  that"  ${LightPurple}
        boxcenter "if the same plugin is processed ultimately to many"  ${LightPurple}
        boxcenter "compute  environments,  an 'already' state will be"  ${LightPurple}
        boxcenter "triggered. This state is harmless and merely is  a"  ${LightPurple}
        boxcenter "warning.                                          "  ${LightPurple}
        echo ""                                                         | ./boxes.sh
    fi
    if (( b_uploadFail > 0 )) ; then
        printf "${LightRed}%16s${Brown}%-64s${NC}\n"                    \
            "$b_uploadFail"                                             \
        " representation(s) did not upload to ChRIS Store."             | ./boxes.sh
        boxcenter "The attempt to upload some plugin representations "  ${LightRed}
        boxcenter "had a complete failure. This could mean that the  "  ${LightRed}
        boxcenter "plugin itself did not exist or download, or if it "  ${LightRed}
        boxcenter "did, the plugin might not correctly service the   "  ${LightRed}
        boxcenter "'--json' flag to create a representation.         "  ${LightRed}
        echo ""                                                         | ./boxes.sh
    fi
windowBottom


title -d 1 "Automatically registering some plugins from the ChRIS store" \
           "with associated compute environment in ChRIS..."
    declare -i i=1
    declare -i b_registerSuccess=0
    declare -i b_registerFail=0
    echo ""                                                     | ./boxes.sh
    echo ""                                                     | ./boxes.sh
    for plugin in "${a_PLUGINRepoEnv[@]}"; do
        cparse $plugin ".py" "REPO" "CONTAINER" "MMN" "ENV"
        echo -en "\033[2A\033[2K"

        printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%23s${blink}${LightGreen}%-17s${NC}\n"  \
        "$i: " "$REPO/$CONTAINER" "[ChRIS]::$ENV<--" "[     adding    ]"        | ./boxes.sh
        windowBottom
        computeDescription="${ENV} description"
        docker-compose -f docker-compose_dev.yml                    \
            exec chris_dev python plugins/services/manager.py       \
            add "$ENV" "http://pfcon.local:5005"                    \
            --description "$ENV Description" >& dc.out >/dev/null
        status=$?
        echo -en "\033[3A\033[2K"
        printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%23s${LightGreen}%-17s${NC}\n"          \
        "$i: " "$REPO/$CONTAINER" "[ChRIS]::$ENV<--" "[ added success ]"        | ./boxes.sh
        cat dc.out | ./boxes.sh
        echo -en "\033[1A\033[2K"
        printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%23s${blink}${LightGreen}%-17s${NC}\n"  \
        "$i: " "$REPO/$CONTAINER" "[ChRIS]::$ENV<--" "[ registering   ]"          | ./boxes.sh
        windowBottom
        docker-compose -f docker-compose_dev.yml                    \
            exec chris_dev python plugins/services/manager.py       \
            register $ENV --pluginname "$CONTAINER"  >& dc.out >/dev/null
        status=$?
        echo -en "\033[3A\033[2K"
        if (( $status == 0 )) ; then
            printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%23s${GreenBG}${White}%-17s${NC}\n"      \
            "$i: " "$REPO/$CONTAINER" "[ChRIS]::$ENV<--" "[ register  OK  ]"    | ./boxes.sh
            b_registerSuccess=$(( b_registerSuccess+=1 ))
        else
            printf "${Yellow}%5s${LightCyan}%-35s${Yellow}%23s${RedBG}${White}%-17s${NC}\n"   \
            "$i: " "$REPO/$CONTAINER" "[ChRIS]::$ENV<--" "[ register fail ]"    | ./boxes.sh
            b_registerFail=$(( b_registerFail+=1 ))
        fi
        cat dc.out | ./boxes.sh
        ((i++))
        windowBottom
    done
    echo -en "\033[2A\033[2K"
    echo ""                                                             | ./boxes.sh
    if (( b_registerSuccess )) ; then
        printf "${LightCyan}%18s${LightGreen}%-62s${NC}\n"              \
            "$b_registerSuccess"                                        \
            " plugin(s)+env(s) successfully registered to ChRIS"        | ./boxes.sh
        echo ""                                                         | ./boxes.sh
    fi
    if (( b_registerFail )) ; then
        printf "${Red}%18s${Brown}%-62s${NC}\n"                         \
            "$b_registerFail"                                           \
            " plugin(s)+env(s)  failed  to  register  to ChRIS."        | ./boxes.sh
        boxcenter "Plugins that failed to register to ChRIS will not"    ${LightRed}
        boxcenter "be available for use in the system.  Please check"    ${LightRed}
        boxcenter "the  plugin  download  and/or  store registration"    ${LightRed}
        boxcenter "steps for possible insights.                     "    ${LightRed}
        echo ""                                                         | ./boxes.sh
    fi
    echo ""                                                             | ./boxes.sh
    windowBottom

