#!/bin/bash

G_SYNOPSIS="

 NAME

	register_plugin.sh

 SYNOPSIS

	register_plugin.sh [--name NAME | --url URL] COMP_ENV

 ARGS

    --name NAME

	    Plugin's name.

    --url URL

	    Plugin's url.

    COMP_ENV

	    Compute environment identifier where the plugin will be executed.

 DESCRIPTION

    register_plugin.sh script will register a plugin from the ChRIS store in ChRIS.
    The plugin must already be previously uploaded to the ChRIS store.

"

if [[ "$#" -lt 3 ]] || [[ "$#" -gt 3 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi

set -e  # terminate as soon as any command fails
COMP_ENV=$3
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
if [[ "$1" == '--url' ]]; then
    PLUGIN_URL=$2
    echo "Registering plugin=$PLUGIN_URL compute environment=$COMP_ENV..."
    docker-compose -f "${DIR}/../../docker-compose.yml" exec chris python plugins/services/manager.py register "$COMP_ENV" --pluginurl "${PLUGIN_URL}"
elif [[ "$1" == '--name' ]]; then
    PLUGIN_NAME=$2
    echo "Registering plugin=$PLUGIN_NAME compute environment=$COMP_ENV..."
    docker-compose -f "${DIR}/../../docker-compose.yml" exec chris python plugins/services/manager.py register "$COMP_ENV" --pluginname "${PLUGIN_NAME}"
else
    echo "--url URL or --name NAME must be provided as the first argument."
    exit 1
fi
echo " "
