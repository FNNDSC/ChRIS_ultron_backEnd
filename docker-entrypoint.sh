#!/bin/bash

# Set the permission on the mounted volume container
# chmod 777 /usr/users

# Start chris server
python manage.py runserver 0.0.0.0:8000

exec "$@"
