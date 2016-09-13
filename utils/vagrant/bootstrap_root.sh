#!/usr/bin/env bash

echo "Provisioning virtual machine..."

apt-get update

echo "Preparing MySQL"
apt-get install debconf-utils -y

# set default mysql root password
debconf-set-selections <<< "mysql-server mysql-server/root_password password 1234"
debconf-set-selections <<< "mysql-server mysql-server/root_password_again password 1234"

echo "Installing Apache2 - dev"
apt-get install apache2-dev -y

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
