#!/usr/bin/env bash
#
# Once a ChRIS/CUBE ecosystem has been fully instantiated from a run of the
# 'make.sh' script, the system will by default only have a few test/dummy
# plugins available. This is to keep instantiation times comparatively fast,
# especially in the case of development where the whole ecosystem is created
# and destroyed multiple times.
#
# In order to add more plugins to an instantiated system, this postscript.sh
# can be used to add plugins and also provide an easy cheat sheet for adding
# more.
#

G_SYNOPSIS="
  NAME
    postscript.sh

  SYNOPSIS
    postscript.sh [swift|fslink|filesystem]

  ARGS
    [swift|fslink|filesystem]
    Denotes the storage environment.

  DESCRIPTION
    postscript.sh script can be used to add plugins to an instantiated system.
"

if [[ "$#" -eq 0 ]] || [[ "$#" -gt 1 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi

STORAGE_ENV=$1

if ! [[ "$STORAGE_ENV" =~ ^(swift|fslink|filesystem)$ ]]; then
    echo "error: Invalid storage environment"
    echo "$G_SYNOPSIS"
    exit 1
fi

if [[ $STORAGE_ENV == 'swift' ]]; then
    docker compose -f docker-compose_dev.yml run --rm chrisomatic chrisomatic postscript.yml
elif [[ $STORAGE_ENV =~ ^(fslink|filesystem)$ ]]; then
    docker compose -f docker-compose_noswift.yml run --rm chrisomatic chrisomatic postscript.yml
fi
