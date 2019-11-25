#!/bin/bash

EXT=""
SWIFTIP=$(ip route | grep -v docker | awk '{if(NF==11) print $9}' | head -n 1)
SWIFTPORT=8080
SWIFTPATHPREFIX=""
PULLDIR="./"
PUSHDIR="./"
ACTION="list"

declare -i Gb_verbose=0

G_SYNOPSIS="

 NAME

	swiftCtl.sh

 SYNOPSIS

	swiftCtl.sh             -A <action>                             \\
                                # If push:                              \\
                                        -D <pushDir>                    \\
                                        -E <extension>                  \\
                                # If pull:                              \\
                                        -O <pullDir>                    \\
                                # All actions:                          \\
                                [-P <SwiftPathPrefix>]                  \\
                                [-S <SWIFTIP>]                          \\
                                [-p <SWIFTPORT>]                        \\
                                [-V]

                                
 ARGS

        -V 
        Be verbose. Typically this means echo the actual swift command.

        -A <action> (Default >> $ACTION <<)
        The action to perform. One of:

          +-----o push
          | +---o pull
          | | +-o list
          | | |
          | | +-> list
          | |          
          | |   List files in swift storage.
          | |
          | |   All actions understand:
          | | 
          | |   -P <SwiftPathPrefix>
          | |   The path prefix to use for swift storage. Note that to conform 
          | |   to CUBE-style conventions, this must be
          | |   
          | |           <cubeUser>/uploads
          | |           
          | |   so the path in swift is:
          | |   
          | |           <cubeUser>/uploads/<uploadPathPrefix>
          | |
          | +---> pull:
          | 
          |     Pull files from swift storage.
          | 
          |             -O <pullDir>
          |             Pull objects from swift to <pullDir>.
          | 
          +----> push:

                Push files to swift storage.

                        -D <pushDir>
                        Examine <pushDir> for files to PUSH.

                        -E <extension>
                        The extension of files in <pushDir> to PUSH 
                        to swift storage.
                


        -S <SWIFTIP>
        The IP address of the swift instance to which files are pushed.
        If not specified will default to >> $SWIFTIP <<.

        -p <SWIFTPORT>
        The port address of the swift instance to which files are pushed.
        If not specified will default to >> $SWIFTPORT <<.
        
 DESCRIPTION
 
        'swiftCtl.sh' is a simple shell script that interacts with a 
        swift container.

"

function synopsis_show
{
        echo "USAGE:"
        echo "$G_SYNOPSIS"
}

function CMD_eval
{
        CMD=$1
        if (( Gb_verbose )) ; then
                echo $CMD
        fi
        eval $CMD
}

while getopts E:C:P:p:A:VO:D:S: option ; do 
	case "$option"
	in
                D)      PUSHDIR=$OPTARG                 ;;
                V)      Gb_verbose=1                    ;;
                O)      PULLDIR=$OPTARG                 ;;
                A)      ACTION=$OPTARG                  ;;
	        P)      SWIFTPATHPREFIX=$OPTARG         ;;
	        p)      SWIFTORT=$OPTARG                ;;
	        E)      EXT=$OPTARG                     ;;
	        S)      SWIFTIP=$OPTARG                 ;;
		\?)     synopsis_show 
                        exit 0;;
	esac
done

case $ACTION 
in
    "push")
        here=$(pwd)
        cd $PUSHDIR
        for FILE in *${EXT} ; do
                if (( Gb_verbose )); then
                        printf "Pushing file: %s to ${SWIFTPATHPREFIX}/$FILE\n" $FILE
                fi
                CMD="swift -U chris:chris1234 -A http://${SWIFTIP}:${SWIFTPORT}/auth/v1.0  -K testing upload users $FILE --object-name ${SWIFTPATHPREFIX}/$FILE"
                CMD_eval "$CMD"
        done
        cd $here
        ;;
    "list")
        if (( ${#SWIFTPATHPREFIX} )) ; then
            CMD="swift -U chris:chris1234 -A http://${SWIFTIP}:${SWIFTPORT}/auth/v1.0  -K testing list users --prefix $SWIFTPATHPREFIX"
        else
            CMD="swift -U chris:chris1234 -A http://${SWIFTIP}:${SWIFTPORT}/auth/v1.0  -K testing list users"
        fi
        CMD_eval "$CMD"
        ;;
    "pull")
        # First, get a listing of files:
        if (( ${#SWIFTPATHPREFIX} )) ; then
            CMD="swift -U chris:chris1234 -A http://${SWIFTIP}:${SWIFTPORT}/auth/v1.0  -K testing list users --prefix $SWIFTPATHPREFIX"
        else
            CMD="swift -U chris:chris1234 -A http://${SWIFTIP}:${SWIFTPORT}/auth/v1.0  -K testing list users"
        fi
        LINELISTING=$(eval $CMD)
        LIST=$(echo $LINELISTING | tr ' ' '\n')
        
        if (( ${#PULLDIR} )) ; then
                OUTPUTDIR="--output-dir $PULLDIR"
        else
                OUTPUTDIR=""
        fi

        for FILE in $LIST ; do
              if (( Gb_verbose )) ; then
                      printf "Pulling file: %s\n" $FILE
              fi
              CMD="swift -U chris:chris1234 -A http://${SWIFTIP}:${SWIFTPORT}/auth/v1.0  -K testing download users $OUTPUTDIR --prefix $FILE"
              CMD_eval "$CMD"
        done
        ;;
esac


