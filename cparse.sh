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
        local str_env=$(echo $pluginSpec | grep -Po '(?<=\^).+$' || echo host)

        # get the repo portion of "repo/name:tag"
        # or produce a default repo, "fnndsc"
        local str_repo=$(echo $str_dock | grep -Po '^.+(?=\/)' || echo $CREPO)
        # get the name:tag portion of "repo/name:tag"
        local str_container="${str_dock#*/}"

        local str_mmn

        # we will use "docker inspect" to find out the executable specified
        # in the container image's Dockerfile by CMD

        # note: instead of using what we were given, $str_dock,
        # we are rebuilding the string by concatention of its parts
        # because above we might have implicitly filled the repo as "fnndsc"
        local json=$(docker image inspect "$str_repo/$str_container" 2> /dev/null)

        if [ "$?" -eq "0" ]; then
                # best way to inspect JSON is to use jq, of course.
                # but we also provide a fallback using coreutils if jq is not installed
                if which jq > /dev/null; then
                        str_mmn=$(echo $json | jq -r '.[0].Config.Cmd[0]')
                else
                        # fallback strategy: use `tr` to join string on line breaks,
                        # because grep operates per-line.
                        # the first `grep` selects the `"Config": {...}` object.
                        # the second `grep` selects the `"Cmd": [...]` array.
                        # finally, `cut` extracts the first string element of the array

                        str_mmn=$(echo $json | tr -d '\n' | grep -m 1 -o '"Config": {.*\}' \
                                | grep -m 1 -Po '(?<="Cmd": \[).+?(?=\])' | cut -d '"' -f2)
                fi
        fi
        # cparse is also (mis-)used in make.sh to parse `A_CONTAINER`
        # the services pman, pfioh, pfcon might not have CMD
        # in this situation we should not fail the script,
        # just return the string value "null" to match what `jq` would produce
        
        # str_mmn will be empty in case of any failures, like docker image was not pulled yet
        str_mmn="${str_mmn:-null}"

        # register results into given variable names
        eval $__repo="'$str_repo'"
        eval $__container="'$str_container'"
        eval $__mainModuleName="'$str_mmn'"
        eval $__env="'$str_env'"
}
