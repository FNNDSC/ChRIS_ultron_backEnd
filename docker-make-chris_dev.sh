#!/bin/bash

echo "1-Changing permissions to 755 for $PWD ..."
chmod -R 755 $(pwd)
echo " "

echo "2-Starting chris containerized development environment from ./docker-compose.yml ..."
echo " "
docker-compose up -d
echo " "

echo "3-Waiting until mysql server is ready to accept connections ..."
docker-compose exec chris_dev_db sh -c 'while ! mysqladmin -uroot -prootp status 2> /dev/null; do sleep 5; done;'
# Give all permissions to chris user in the DB. This is required for the Django tests:
docker-compose exec chris_dev_db mysql -uroot -prootp -e 'GRANT ALL PRIVILEGES ON *.* TO "chris"@"%"'
echo " "

echo "4-Making migrations"
docker-compose exec chris_dev python manage.py migrate
echo " "

echo "5-Registering plugins ..."
# Declare an array variable for the list of plugin dock images
# Add a new plugin image name to the list if you want it to be automatically registered
docker-compose exec chris_dev /bin/bash -c \
  'declare -a plugins=("fnndsc/pl-simplefsapp"
                       "fnndsc/pl-simpledsapp"
                       "fnndsc/pl-pacsquery"
                       "fnndsc/pl-pacsretrieve"
                      )
   for plugin in "${plugins[@]}"; do python3 plugins/services/manager.py --add ${plugin} 2> /dev/null; done'
echo " "

echo "6-Running Django tests ..."
docker-compose exec chris_dev python manage.py test
echo " "

echo "7-Restarting Djando development server ..."
docker-compose restart chris_dev
echo " "

echo "8-Now create two chris API users"
echo 'Please name one of the users as "chris"'
echo " "
docker-compose exec chris_dev python manage.py createsuperuser
docker-compose exec chris_dev python manage.py createsuperuser

echo "9-Restarting Djando development server in interactive mode ..."
docker-compose stop chris_dev
docker-compose rm -f chris_dev
docker-compose run --service-ports chris_dev
echo " "
