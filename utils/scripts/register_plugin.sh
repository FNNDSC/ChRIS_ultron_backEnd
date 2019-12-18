#!/bin/bash

G_SYNOPSIS="

 NAME

	register_plugin.sh

 SYNOPSIS

	register_plugin.sh PLUGIN COMP_ENV

 ARGS

    PLUGIN

	    Plugin's name.

    COMP_ENV

	    Compute environment identifier where the plugin will be executed.

 DESCRIPTION

	register_plugin.sh script will register a plugin from the ChRIS store in ChRIS.
    The plugin must already be previously uploaded to the ChRIS store.

"

if [[ "$#" -lt 2 ]] || [[ "$#" -gt 2 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi

PLUGIN=$1
COMP_ENV=$2
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
echo "Registering plugin=$PLUGIN  compute environment=$COMP_ENV..."
echo " "
docker-compose -f "${DIR}/../../docker-compose.yml" exec chris python plugins/services/manager.py add "${PLUGIN}" "$COMP_ENV" http://chrisstore:8010/api/v1/
echo " "
