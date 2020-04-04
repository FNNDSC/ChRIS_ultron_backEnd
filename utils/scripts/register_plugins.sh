#!/bin/bash

G_SYNOPSIS="

 NAME

	register_plugins.sh

 SYNOPSIS

	register_plugins.sh FILE [--url]

 ARGS

    FILE

        A text file containing two strings per line (separated by white spaces)
        indicating a plugin's name or url and its associated compute environment
        respectively.

    --url

        Optional flag to indicate that the first string for each line in FILE is the
        plugin's url. If the --url flag is not specified then the first string is
        assumed to be the plugin's name.

 DESCRIPTION

    register_plugins.sh script will register a list of plugins from the ChRIS store in
    ChRIS. The script reads each plugin's name or url and its associated compute
    environment line by line from the FILE argument. Any plugin in the file must already
    be previously uploaded to the ChRIS store.

"

if [[ "$#" -eq 0 ]] || [[ "$#" -gt 2 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi
FILE=$1
if [[ "$#" -eq 2 ]]; then
    if [[ "$1" != '--url' ]] && [[ "$2" != '--url' ]]; then
        echo "$G_SYNOPSIS"
        exit 1
    fi
    if [[ "$1" == '--url' ]]; then
        FILE=$2
    fi
fi
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
    if [[ "$1" == '--url' ]] || [[ "$2" == '--url' ]]; then
        "${DIR}/register_plugin.sh" --url $plugin $compute_env
    else
       "${DIR}/register_plugin.sh" --name $plugin $compute_env
    fi
    ((i++))
done
