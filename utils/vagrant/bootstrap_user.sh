#!/usr/bin/env bash

#!/usr/bin/env bash

chrisDirectory="chris-ultron-backend"
userHome="/home/ubuntu"
virtualEnvironment="chris-ultron"
virtualEnvironmentDirectory="python-envs"
workingDirectory="/home/ubuntu"

G_SYNOPSIS="
 NAME
       bootstrap.bash
 SYNOPSIS
       bootstrap.bash -c <chrisDirectory> -u <userHome> -v <virtualEnvironment> -d <virtualEnvironmentDirectory> -w <workingDirectory>
 DESCRIPTION
        'bootstrap.bash' setup a development environment for ChRIS Ultron
 ARGS
	-c <chrisDirectory> (defaults to: $chrisDirectory)
	The directory containing the chris source code within <workingDirectory>.
	-u <userHome> (defaults to: $userHome)
	The user home directory to configure the .bashrc automatically.
	-v <virtualEnvironment> (defaults to: $virtualEnvironment)
	The name of the python virtual environment for chris.
	-d <virtualEnvironmentDirectory> (defaults to: $virtualEnvironmentDirectory)
	The directory containing the virtual python environment within <workingDirectory>.
	-w <workingDirectory> (defaults to: $workingDirectory)
	The 'working' directory that contains the <virtualEnvironmentDirectory> and
        the <chrisDirectory>
"

while getopts u:h:n: option ; do
        case "$option"
        in
                c)      chrisDirectory=$OPTARG			;;
                u)      userHome=$OPTARG			;;
                v)      virtualEnvironment=$OPTARG	        ;;
                d)      virtualEnvironmentDirectory="$OPTARG"   ;;
                w)      workingDirectory="$OPTARG"              ;;
                \?)     echo "$G_SYNOPSIS"
                        exit 0;;
        esac
done

echo "Preparing Python Virtual Env"

_python_virtual_env_dir="$workingDirectory/$virtualEnvironmentDirectory"
_user_bashrc="$userHome/.bashrc"

mkdir -p $_python_virtual_env_dir
echo "export WORKON_HOME=$_python_virtual_env_dir" >> $_user_bashrc
echo "source /usr/local/bin/virtualenvwrapper.sh" >> $_user_bashrc
echo "workon $virtualEnvironment" >> $_user_bashrc
export WORKON_HOME=$_python_virtual_env_dir
source /usr/local/bin/virtualenvwrapper.sh

echo "Creating Python Virtual Env"
mkvirtualenv --python=python3 $virtualEnvironment

echo "Activating Python Virtual Env"
workon $virtualEnvironment

echo "Installing Python requirements/local"

_chris_directory="$workingDirectory/$chrisDirectory"
cd $_chris_directory
pip install -r requirements/local.txt

echo "Installing Sphinx"
pip install Sphinx sphinxcontrib-httpdomain
