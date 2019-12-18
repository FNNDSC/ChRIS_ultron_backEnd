#!/bin/bash

G_SYNOPSIS="

 NAME

	upload_plugins.sh

 SYNOPSIS

	upload_plugins.sh USER FILE

 ARGS

    USER

	    The user that will own the plugins in the ChRIS store.

	FILE

	    A text file containing three strings per line (separated by white spaces) \
        indicating a plugin's name, docker image and public source code repo respectively.

 DESCRIPTION

	upload_plugins.sh script will upload a list of plugins to the ChRIS store under the \
    same ChRIS store user account. The script reads each plugin's name, docker image and\
    source code repo line by line from the FILE argument.

"

if [[ "$#" -lt 2 ]] || [[ "$#" -gt 2 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi

USER=$1
FILE=$2
PLUGIN_ARRAY=()
DOCK_ARRAY=()
REPO_ARRAY=()
while read -r plugin dock repo; do
    PLUGIN_ARRAY+=($plugin)
    DOCK_ARRAY+=($dock)
    REPO_ARRAY+=($repo)
done < "$FILE"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
declare -i i=1
for index in "${!PLUGIN_ARRAY[@]}"; do
    plugin=${PLUGIN_ARRAY[$index]}
    dock=${DOCK_ARRAY[$index]}
    repo=${REPO_ARRAY[$index]}
    echo "[$i]"
    "${DIR}/upload_plugin.sh" $USER $plugin $dock $repo
    ((i++))
done
