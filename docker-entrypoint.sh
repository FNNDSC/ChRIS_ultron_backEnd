#!/bin/bash

# Set the permission on the mounted volume container
# chmod 777 /usr/users

# Start ChRIS server
python check_db_connection.py -u root -p rootp --host chris_dev_db --max-attempts 30
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

exec "$@"
