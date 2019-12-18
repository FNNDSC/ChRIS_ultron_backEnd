#!/bin/bash

G_SYNOPSIS="

 NAME

	upload_plugin.sh

 SYNOPSIS

	upload_plugins.sh USER PLUGIN DOCK REPO

 ARGS

    USER

	    The user that will own the plugin in the ChRIS store.

    PLUGIN

	    Plugin's name.

    DOCK

	    Plugin's docker image.

    REPO

	    Plugin's public source code repo respectively.

 DESCRIPTION

	upload_plugin.sh script will upload a plugin to the ChRIS store.

"

if [[ "$#" -lt 4 ]] || [[ "$#" -gt 4 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi

USER=$1
PLUGIN=$2
DOCK=$3
REPO=$4
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
echo "Uploading user=$USER  plugin=$PLUGIN  image=$DOCK  repo=$REPO..."
echo " "
docker pull $DOCK
PLUGIN_REP=$(docker run --rm "${DOCK}" "${PLUGIN}.py" --json 2> /dev/null;)
docker-compose -f "${DIR}/../../docker-compose.yml" exec chrisstore python plugins/services/manager.py add "$PLUGIN" "$USER" "$REPO" "$DOCK" --descriptorstring "$PLUGIN_REP"
echo " "
