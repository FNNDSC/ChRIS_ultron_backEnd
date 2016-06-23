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

echo "Provisioning virtual machine..."

apt-get update

echo "Preparing MySQL"
apt-get install debconf-utils -y

# set default mysql root password
debconf-set-selections <<< "mysql-server mysql-server/root_password password 1234"
debconf-set-selections <<< "mysql-server mysql-server/root_password_again password 1234"

echo "Installing MySQL"
apt-get install mysql-server libmysqlclient-dev -y

echo "Initiating MySQL Databases"
echo "CREATE DATABASE chris_dev CHARACTER SET utf8;GRANT ALL ON chris_dev.* TO 'chris'@'localhost' IDENTIFIED BY 'Chris1234';    GRANT ALL ON test_chris_dev.* TO 'chris'@'localhost' IDENTIFIED BY 'Chris1234';" | mysql -u root -p1234

echo "Installing Python"
apt-get install python3-dev -y

echo "Installing PIP"
apt-get install python-pip -y

echo "Upgrading PIP"
pip install --upgrade pip

echo "Installing Python Vitual Env"
pip install virtualenv virtualenvwrapper

echo "Preparing Python Virtual Env"

_python_virtual_env_dir="$workingDirectory/$virtualEnvironmentDirectory"
_user_bashrc="$userHome/.bashrc"

mkdir -p $_python_virtual_env_dir
echo "export WORKON_HOME=$_python_virtual_env_dir" >> $_user_bashrc
echo "source /usr/local/bin/virtualenvwrapper.sh" >> $_user_bashrc
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

