#!/bin/bash

echo "1-Changing permissions to 755 for $PWD ..."
chmod 755 -R $(pwd)
echo " "

echo "2-Starting chris containerized development environment from ./docker-compose.yml ..."
echo " "
docker-compose up -d
echo " "

echo "3-Waiting until mysql server is ready to accept connections ..."
docker-compose exec chris_dev_db sh -c 'while ! mysqladmin -uroot -prootp status 2> /dev/null; do sleep 5; done;'
# Give allpermissions to chris user in the DB. This is required for the Django tests:
docker-compose exec chris_dev_db mysql -uroot -prootp -e 'GRANT ALL PRIVILEGES ON *.* TO "chris"@"%"'
echo " "

echo "4-Making migrations"
docker-compose exec chris_dev python manage.py migrate
echo " "

echo "5-Registering plugins ..."
docker-compose exec chris_dev sh -c 'for i in $(ls -d plugins/services/*/); do if [ -f ${i}$(basename ${i}).py ]; then python3 plugins/services/manager.py --add $(basename ${i}) 2> /dev/null; fi; done'
echo " "

echo "6-Running Django tests ..."
docker-compose exec chris_dev python manage.py test
echo " "

echo "7-Restarting Djando development server ..."
docker-compose restart chris_dev
echo " "

echo "8-Now create three chris API users"
echo 'Please name one of the users as "chris"'
echo " "
docker-compose exec chris_dev python manage.py createsuperuser
docker-compose exec chris_dev python manage.py createsuperuser
docker-compose exec chris_dev python manage.py createsuperuser
