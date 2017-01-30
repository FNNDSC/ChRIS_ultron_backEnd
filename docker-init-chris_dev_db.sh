#!/bin/bash

echo "Initializing chris_dev database"

export chris="'chris'@'$1'"

mysql -u root -p"$MYSQL_ROOT_PASSWORD" << EOF
CREATE DATABASE chris_dev CHARACTER SET utf8;
GRANT ALL ON chris_dev.* TO $chris IDENTIFIED BY 'Chris1234';
GRANT ALL PRIVILEGES ON *.* TO $chris;
EOF
