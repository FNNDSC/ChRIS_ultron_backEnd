#!/bin/bash

EXT=""
CUBEIP=$(ip route | grep -v docker | awk '{if(NF==11) print $9}')
CUBEPORT=8000
UPLOADPATHPREFIX="externalData"
PUSHDIR="./"
G_SYNOPSIS="

 NAME

	pushAllToCube.sh

 SYNOPSIS

	pushAllToCube.sh         -E <extension>                         \\
                                [-D <pushDir>]                          \\
	                        [-P <uploadPathPrefix>]                 \\
                                [-C <CUBE_IP>]                          \\
                                [-p <CUBE_port>]
                                
 ARGS
 
        -E <extension>
        The extension of files to PUSH to CUBE swift storage

        -D <pushDir>
        The directory containing files to PUSH.
        
        -P <uploadPathPrefix>
        The upload prefix to use for swift storage. Note that the backend
        prepends the following pattern to <uploadPathPrefix>:
        
                <cubeUser>/uploads
                
        so the path in swift is:
        
                <cubeUser>/uploads/<uploadPathPrefix>

        DO NOT PREPEND THIS PATH WITH A '/'!
        
        -C <CUBE_IP>
        The IP address of the CUBE instance to which files are pushed.
        If not specified will default to >> $CUBEIP <<.

        -p <CUBE_port>
        The port address of the CUBE instance to which files are pushed.
        If not specified will default to >> $CUBEPORT <<.

        
 DESCRIPTION
 
        'pushAllToCube.sh' is a simple shell script that calls the CUBE
        API to upload files, specified by <extension> in the current
        directory.


"


function synopsis_show
{
        echo "USAGE:"
        echo "$G_SYNOPSIS"
}

while getopts E:C:P:p:D: option ; do 
	case "$option"
	in
                D)      PUSHDIR=$OPTARG                 ;;
	        P)      UPLOADPATHPREFIX=$OPTARG        ;;
	        p)      CUBEPORT=$OPTARG                ;;
	        E)      EXT=$OPTARG                     ;;
	        C)      CUBEIP=$OPTARG                  ;;
		\?)     synopsis_show 
                        exit 0;;
	esac
done

here=$(pwd)
cd $PUSHDIR
for FILE in *${EXT} ; do
    printf "%s\n" $FILE
    http -a cube:cube1234 -f POST http://${CUBEIP}:${CUBEPORT}/api/v1/uploadedfiles/ upload_path=/${UPLOADPATHPREFIX}/$FILE fname@$FILE
done
cd $here

printf "Files pushed to swift service.\n"
swiftQuery="

swift -A http://${CUBEIP}:8080/auth/v1.0 -U chris:chris1234 -K testing list users

"

runPluginCmd="

pfurl --auth cube:cube1234 --verb POST --http ${CUBEIP}:${CUBEPORT}/api/v1/plugins/8/instances/ \\
--content-type application/vnd.collection+json \\
--jsonwrapper 'template' --msg '
{\"data\":
    [{\"name\":\"dir\",
      \"value\":\"/${UPLOADPATHPREFIX}\"}
    ]
}' \\
--quiet --jsonpprintindent 4

"

registerOutputFilesCmd="

pfurl --auth chris:chris1234                               \\
      --verb GET                                           \\
      --http ${CUBEIP}:${CUBEPORT}/api/v1/plugins/instances/1/   \\
      --content-type application/vnd.collection+json       \\
      --quiet --jsonpprintindent 4
"


printf "Run the pl-dircopy plugin to pull this data from swift storage into CUBE:\n"
printf "$runPluginCmd"
printf "\n"
printf "Trigger output file registration in CUBE with:\n"
printf "$registerOutputFilesCmd"
printf "\n"
printf "Query swift with:\n"
printf "$swiftQuery"



