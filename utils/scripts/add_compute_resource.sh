#!/bin/bash

G_SYNOPSIS="

 NAME

	add_compute_resource.sh

 SYNOPSIS

	add_compute_resource.sh NAME DESCRIPTION

 ARGS

    NAME

	    Compute resource's name.

    DESCRIPTION

	    Compute resource's description.

 DESCRIPTION

    add_compute_resource.sh script will add a new compute resource to ChRIS.

"

if [[ "$#" -lt 2 ]] || [[ "$#" -gt 2 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi

NAME=$1
DESCRIPTION=$2

set -e  # terminate as soon as any command fails

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
echo " "
    echo "Adding $NAME compute resource..."
    docker-compose -f "${DIR}/../../docker-compose.yml" exec chris python plugins/services/manager.py add "${NAME}" "${DESCRIPTION}"
echo " "
