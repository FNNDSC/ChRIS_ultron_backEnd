#!/bin/bash

python check_db_connection.py -u root -p $MYSQL_ROOT_PASSWORD --host $DATABASE_HOST --max-attempts 30
python manage.py migrate
python manage.py collectstatic

exec "$@"
