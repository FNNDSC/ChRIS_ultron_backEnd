#!/bin/bash
#
# NAME
#
#   boxes.sh
#
# DESC
#
#   Draws left and right "box" outlines for a string of text
#   in line by line fashion -- useful to create the "body" of
#   a box of text, for example:
#
#       │      Here is some text that          │▒ 
#       │      is created in a box of          │▒ 
#       │      some fixed width, with          │▒ 
#       │      a shadow effect also!           │▒ 
#

. ./decorate.sh
let width=80
let b_clear=0


while getopts "c" opt; do
    case $opt in
        c) b_clear=1;;
	esac
done

shift "$((OPTIND-1))"

# Set the default line color
if (( $# != 1 )) ; then
	set -- ${White}
fi

# Grab the default or CLI passed color
lineColor=$1


if ((b_clear)) ; then
        echo -en "\033[2A\033[2K"
fi

while IFS= read line; do
	line="$(echo -e "${line}" | sed -e 's/[[:space:]]*$//')"
	LINELEN=${#line}
	TRAILLEN=$(( $width - $LINELEN ))
	PADDING=""
	if (( TRAILLEN > 0 )) ; then
		PADDING=$(head -c $TRAILLEN < /dev/zero | tr '\0' ' ')
	fi
	printf "${Yellow}│${lineColor}${line}${PADDING}${Yellow}│${Brown}▒${NC}\n"
done
