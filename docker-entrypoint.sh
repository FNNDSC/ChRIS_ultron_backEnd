#!/bin/bash

if [[ "$DJANGO_DB_MIGRATE" == 'on' ]]; then
  if [[ "$DJANGO_SETTINGS_MODULE" == 'config.settings.local' ]]; then
    python migratedb.py -u root -p rootp --host chris_dev_db --noinput
  elif [[ "$DJANGO_SETTINGS_MODULE" == 'config.settings.production' ]]; then
    python migratedb.py -u root -p $MYSQL_ROOT_PASSWORD --host $DATABASE_HOST --noinput
  fi
fi

if [[ "$DJANGO_COLLECTSTATIC" == 'on' ]]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
