#!/bin/bash

G_SYNOPSIS="

 NAME

	register_plugins.sh

 SYNOPSIS

	register_plugins.sh FILE

 ARGS

	FILE

	    A text file containing two strings per line (separated by white spaces) \
        indicating a plugin's name and compute environment respectively.

 DESCRIPTION

	register_plugins.sh script will register a list of plugins from the ChRIS store in \
    ChRIS. The script reads each plugin's name and compute environment line by line from \
    the FILE argument. Any plugin in the file must already be previously uploaded to the
    ChRIS store.

"

if [[ "$#" -eq 0 ]] || [[ "$#" -gt 1 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi

FILE=$1
PLUGIN_ARRAY=()
COMPUTE_ENV_ARRAY=()
while read -r plugin compute_env; do
    PLUGIN_ARRAY+=($plugin)
    COMPUTE_ENV_ARRAY+=($compute_env)
done < "$FILE"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
declare -i i=1
for index in "${!PLUGIN_ARRAY[@]}"; do
    plugin=${PLUGIN_ARRAY[$index]}
    compute_env=${COMPUTE_ENV_ARRAY[$index]}
    echo "[$i]"
    "${DIR}/register_plugin.sh" $plugin $compute_env
    ((i++))
done
