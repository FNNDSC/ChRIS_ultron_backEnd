#!/bin/bash

echo "Creating chris containerized development environment"
echo " "

echo "1-Creating a volume container for the chrid db data"
docker run -d -v /var/lib/mysql --name chris_dev_db_data alpine echo DB Data Container
echo " "

echo "2-Starting mysql in a container mounting the previous volume container and docker-init-chris_dev_db.sh file ..."
docker run --name chris_dev_db --volumes-from chris_dev_db_data -v "$PWD/docker-init-chris_dev_db.sh":/docker-init-chris_dev_db.sh -e MYSQL_ROOT_PASSWORD=rootp -d mysql:5
echo " "

echo "3-Starting chris development environment container with access to the previous mysql container ..."
docker run --name chris_dev --link chris_dev_db:mysql -v "$PWD/chris_backend":/usr/src/chris_backend -p 8000:8000 -d fnndsc/chris_dev_backend:local
export chris_dev_IP="$(docker inspect --format '{{.NetworkSettings.IPAddress}}' chris_dev)"
echo " "

echo "4-Initializing chris_dev DB" 
echo "Waiting 30 seconds for chris development server to stabilize..."
sleep 30
docker exec chris_dev_db ./docker-init-chris_dev_db.sh $chris_dev_IP
echo " "

echo "5-Making migrations"
docker exec chris_dev python3 manage.py migrate
echo " "

echo "6-Restarting Djando development server ..."
docker restart chris_dev
echo " "

echo "7-Now create three chris API users"
echo 'Please name one of the users as "chris"' 
docker exec -it chris_dev python3 manage.py createsuperuser
docker exec -it chris_dev python3 manage.py createsuperuser
docker exec -it chris_dev python3 manage.py createsuperuser



 
