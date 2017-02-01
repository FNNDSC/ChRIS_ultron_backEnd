#!/bin/bash

echo "Destroying chris development containerized environment"
echo " "

echo "1-Stopping Django development server ..."
docker stop chris_dev
echo " "

echo "2-Stopping Chris MySql DB container ..."
docker stop chris_dev_db
echo " "

echo "3-Removing all containers"
docker rm -vf chris_dev chris_dev_db chris_dev_db_data

 
