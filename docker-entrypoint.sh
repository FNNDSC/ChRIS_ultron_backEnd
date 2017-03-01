#!/bin/bash

# Start chris server
python manage.py runserver 0.0.0.0:8000
# Start pman server
pman --raw 1 --http  --port 5010 --listeners 12

exec "$@"
