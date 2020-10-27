#!/bin/bash
#
# NAME
#
#       cparse.sh
#
# SYNOPSIS
#
#       cparse.sh <cstring> "REPO" "CONTAINER" "MMN" "ENV"
#
# DESCRIPTION
#
#       cparse.sh parses a <cstring> of pattern:
#
#               [<repo>/]<container>[::<mainModuleName>[%<extension>[^<env>]]]
#
#       and returns
#
#               <repo> <container> <mainModuleName><extension> <env>
#
# ARGS
#
# <string>
#
#       The container name string to parse.
#
#
# RETURN
#
# REPO
#       if not passed in <repo>, defaults to env variable, $CREPO.
#
# CONTAINER
#
#       the <container> part of the string.
#
# MMN
#       if not passed, defaults to the <container> string
#
# EXT
#       if not passed, defaults to empty.
#
# ENV
#       if not passed, defaults to "host", else <env>.
#
# EXAMPLE
#
#       source cparse.sh
#       cparse_do "local/pl-dircopy::directoryCopy:%.py^moc"
#


CREPO=fnndsc

function cparse {
        pluginSpec=$1

        local __repo=$2
        local __container=$3
        local __mainModuleName=$4
        local __env=$5

        export pluginSpec=$pluginSpec
        export CREPO=$CREPO

l_parse=$(python3 - << EOF
import os

b_done          = False

str_pluginSpec  = os.environ['pluginSpec']
str_CREPO       = os.environ['CREPO']

# [<repo>/]
l_spec          = str_pluginSpec.split('/')
if len(l_spec) == 1:
        # No leading [<repo>/]
        str_repo        = str_CREPO
        str_remain      = l_spec[0]
else:
        # There is a leading [<repo>/]
        str_repo        = l_spec[0]
        str_remain      = l_spec[1]

# [^<env>]
l_spec          = str_remain.split('^')
if len(l_spec) == 1:
        # No trailing [^<env>]
        str_env         = 'host'
        str_remain      = l_spec[0]
else:
        # There is a trailing [^<env>]
        str_env         = l_spec[1]
        str_remain      = l_spec[0]

# [:<extension]
l_spec          = str_remain.split('%')
if len(l_spec) == 1:
        # No trailing [%<extension>]
        str_extension   = ""
        str_remain      = l_spec[0]
else:
        # There is a trailing [%<extension>]
        str_extension   = l_spec[1]
        str_remain      = l_spec[0]

# [::<mainModuleName]
l_spec          = str_remain.split('::')
if len(l_spec) == 1:
        # No trailing [::<mainModuleName>]
        l_mmn           = l_spec[0].split('pl-')
        if len(l_mmn) == 1:
                str_mmn = l_spec[0]
        else:
                str_mmn = l_mmn[1]
        str_remain      = l_spec[0]
else:
        # There is a trailing [::<mainModuleName>]
        str_mmn         = l_spec[1]
        str_remain      = l_spec[0]



str_container           = str_remain

print("%s %s %s%s %s" % (str_repo, str_container, str_mmn, str_extension, str_env))

EOF
)
        str_repo=$(         echo $l_parse | awk '{print $1}'    )
        str_container=$(    echo $l_parse | awk '{print $2}'    )
        str_mmn=$(          echo $l_parse | awk '{print $3}'    )
        str_env=$(          echo $l_parse | awk '{print $4}'    )

        eval $__repo="'$str_repo'"
        eval $__container="'$str_container'"
        eval $__mainModuleName="'$str_mmn'"
        eval $__env="'$str_env'"

}

function cparse_do {
        TESTNAME="local/pl-dircopy::directoryCopy%.py^moc"

        cparse "$1" "REPO" "CONTAINER" "MMN" "ENV"

        echo $REPO
        echo $CONTAINER
        echo $MMN
        echo $ENV
}


