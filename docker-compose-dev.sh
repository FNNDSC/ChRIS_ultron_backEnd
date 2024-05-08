#!/bin/bash

# change to directory where this script lives
cd "$(dirname "$(readlink -f "$0")")"

set -ex
docker compose -f docker-compose-dev.yml up -d
exec docker compose -f docker-compose-dev.yml run --rm $notty chrisomatic
