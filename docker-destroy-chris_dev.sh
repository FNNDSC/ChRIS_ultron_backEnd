#!/bin/bash

echo "Destroying ChRIS containerized development environment from ./docker-compose.yml"
echo " "

echo "1: Stopping services..."
docker-compose stop
echo " "

echo "2: Removing all containers..."
docker-compose rm -vf 
