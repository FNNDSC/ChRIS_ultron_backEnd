#!/bin/bash
# set up secrets/*.env
# https://github.com/FNNDSC/ChRIS_ultron_backEnd/wiki/ChRIS-backend-production-services-secret-configuration-files
# TODO: ALLOWED_HOSTS not star

# Create a random mixed-case alphanumieric string of given length (default 60)
function generate_password () {
  head /dev/urandom | tr -dc A-Za-z0-9 | head -c "${1:-60}"
}

# check that a list of variables have all been set
function assert_declared () {
  for var; do
    if [ ! -v $var ]; then
      echo "$var is a required variable"
      return 1
    fi
  done
}

source_dir=$(dirname "$(readlink -f "$0")")
secrets_dir=$source_dir/secrets

if [ -d "$secrets_dir" ]; then
  echo $secrets_dir already exists
  exit 1
fi

required_variable_names=(
)

optional_variable_names=(
  DJANGO_CORS_ORIGIN_ALLOW_ALL
  DJANGO_CORS_ORIGIN_WHITELIST
)

assert_declared $required_variable_names || exit $?
DJANGO_CORS_ORIGIN_ALLOW_ALL=${DJANGO_CORS_ORIGIN_ALLOW_ALL:-true}
DJANGO_CORS_ORIGIN_WHITELIST=${DJANGO_CORS_ORIGIN_WHITELIST:-"babymri.org"}

mkdir $secrets_dir
cd $secrets_dir

cat > .chris.env << EOF
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_ALLOWED_HOSTS=*
DJANGO_SECRET_KEY=$(generate_password)
DJANGO_CORS_ORIGIN_ALLOW_ALL=$DJANGO_CORS_ORIGIN_ALLOW_ALL
DJANGO_CORS_ORIGIN_WHITELIST=$DJANGO_CORS_ORIGIN_WHITELIST
STATIC_ROOT=/home/localuser/mod_wsgi-0.0.0.0:8000/htdocs/static/
DATABASE_HOST=chris_db
DATABASE_PORT=3306
CHRIS_STORE_URL=http://chrisstore:8010/api/v1/
SWIFT_CONTAINER_NAME=users
SWIFT_AUTH_URL=http://swift_service:8080/auth/v1.0
CELERY_BROKER_URL=amqp://queue:5672
PFCON_URL=http://pfcon_service:5005
EOF

cat > .chris_db.env << EOF
MYSQL_ROOT_PASSWORD=$(generate_password)
MYSQL_DATABASE=chris
MYSQL_USER=chris
MYSQL_PASSWORD=$(generate_password)
EOF

cat > .chris_store.env << EOF
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_ALLOWED_HOSTS=*
DJANGO_SECRET_KEY=$(generate_password)
DJANGO_CORS_ORIGIN_ALLOW_ALL=$DJANGO_CORS_ORIGIN_ALLOW_ALL
DJANGO_CORS_ORIGIN_WHITELIST=$DJANGO_CORS_ORIGIN_WHITELIST
DATABASE_HOST=chris_store_db
DATABASE_PORT=3306
SWIFT_AUTH_URL=http://swift_service:8080/auth/v1.0
SWIFT_CONTAINER_NAME=store_users
EOF

cat > .chris_store_db.env << EOF
MYSQL_ROOT_PASSWORD=$(generate_password)
MYSQL_DATABASE=chris_store
MYSQL_USER=chris
MYSQL_PASSWORD=$(generate_password)
EOF

cat > .pfcon_service.env << EOF
PFCON_USER=
PFCON_PASSWORD=
EOF

# this is hard coded
cat > .swift_service.env << EOF
SWIFT_USERNAME=chris:chris1234
SWIFT_KEY=testing
EOF

# wrapper around generate_password to print a newline after the result
function print_password () {
  generate_password $1
  printf "\n"
}

echo "Here are some more passwords for you to use for when setting up superuser accounts"
print_password 8
print_password 8
print_password 8
print_password 8
print_password 12
print_password 12
print_password 12
print_password 12
print_password 60
print_password 60
print_password 60
print_password 60
