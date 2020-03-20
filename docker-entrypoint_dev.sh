#!/bin/bash

python check_db_connection.py -u root -p rootp --host chris_dev_db --max-attempts 30
python manage.py migrate

exec "$@"
