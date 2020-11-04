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
#       cparse.sh produces information about a container image, e.g.
#
#               fnndsc/pl-app
#
#       And optionally splices out a trailing string after the "^"
#       character and saves it as "env" (this is an odd legacy spec) e.g.
#
#               fnndsc/pl-app^moc
#
#       and returns
#
#               <repo> <container> <executable> <env>
#
#       where <executable> is the runnable binary specified by Dockerfile CMD
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
#       executable inside the container image, set by CMD inof Dockerfile.
#       If image was not pulled, MMN will be "null"
#
# ENV
#       if not passed, defaults to "host", else <env>.
#
# EXAMPLE
#
#       cparse fnndsc/pl-pfdicom_tagextract repo container mmn env
#       echo $repo $container $mmn $env
#


CREPO=fnndsc

function cparse {
        local pluginSpec=$1

        local __repo=$2
        local __container=$3
        local __mainModuleName=$4
        local __env=$5

        # remove trailing "^moc" if present, resulting in a normal
        # docker image name e.g. fnndsc/chris or fnndsc/chris:latest
        local str_dock="${pluginSpec%\^*}"
        local str_env=host
        if [ "$pluginSpec" != "$str_dock" ]; then
                str_env=$(echo $pluginSpec | sed 's/^.*\^//')
        fi

        # get the repo portion of "repo/name:tag"
        # or produce a default repo, "fnndsc"
        local str_repo=fnndsc
        if [[ "$str_dock" == *"/"* ]]; then
                str_repo=$(echo $str_dock | sed 's/\/.*$//')
        fi
        # get the name:tag portion of "repo/name:tag"
        local str_container="${str_dock#*/}"

        local str_mmn

        # we will use "docker inspect" to find out the executable specified
        # in the container image's Dockerfile by CMD

        # note: instead of using what we were given, $str_dock,
        # we are rebuilding the string by concatention of its parts
        # because above we might have implicitly filled the repo as "fnndsc"
        
        # cparse is also (mis-)used in make.sh to parse `A_CONTAINER`
        # the services pman, pfioh, pfcon might not have CMD
        # so the else block sets str_mmn to "ERR_NO_CMD"
        local str_mmn=$(docker image inspect --format \
                '{{with .Config.Cmd}}{{(index . 0)}}{{else}}ERR_NO_CMD{{end}}' \
                "$str_repo/$str_container" 2> /dev/null)

        # in case docker insepct fails (like when image hasn't been pulled yet)
        # an error is printed to stderr and a newline character is printed to stdout
        # if $str_mmn is just whitespace, assume image hasn't been pulled yet
        if [[ "$str_mmn" =~ ^[[:space:]]*$ ]]; then
                str_mmn=ERR_IMAGE_NOT_PULLED
        fi

        # register results into given variable names
        eval $__repo="'$str_repo'"
        eval $__container="'$str_container'"
        eval $__mainModuleName="'$str_mmn'"
        eval $__env="'$str_env'"
}
