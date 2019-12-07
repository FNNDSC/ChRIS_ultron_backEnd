#!/bin/bash

# Start ChRIS server
python check_db_connection.py -u root -p $MYSQL_ROOT_PASSWORD --host $DATABASE_HOST --max-attempts 30
python manage.py migrate
#python manage.py collectstatic
mod_wsgi-express start-server config/wsgi.py --host 0.0.0.0 --port 8000 --processes 8 --server-root ~/mod_wsgi-0.0.0.0:8000
#mod_wsgi-express setup-server config/wsgi.py --host 0.0.0.0 --port 8000 --processes 8 --server-name localhost --server-root ~/mod_wsgi-0.0.0.0:8000
#to start daemon:
#~/mod_wsgi-0.0.0.0:8000/apachectl start
#to stop deamon
#~/mod_wsgi-0.0.0.0:8000/apachectl stop

exec "$@"
