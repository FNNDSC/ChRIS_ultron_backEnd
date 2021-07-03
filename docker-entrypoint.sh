#!/bin/bash

if [[ "$DJANGO_DB_MIGRATE" == 'on' ]]; then
  if [[ "$DJANGO_SETTINGS_MODULE" == 'config.settings.local' ]]; then
    python migratedb.py -u chris -p Chris1234 -d chris_dev --host chris_dev_db --noinput
  elif [[ "$DJANGO_SETTINGS_MODULE" == 'config.settings.production' ]]; then
    python migratedb.py -u $POSTGRES_USER -p $POSTGRES_PASSWORD -d $POSTGRES_DB --host $DATABASE_HOST --noinput
  fi
fi

if [[ "$DJANGO_COLLECTSTATIC" == 'on' ]]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
