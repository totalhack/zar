#! /usr/bin/env bash

# Exit in case of error
set -e

if [[ ! ("$#" == 1) ]]; then 
    echo 'Please pass a migration revision message'
    exit 1
fi

docker-compose run --rm --entrypoint "alembic -c /app/alembic.ini revision --autogenerate -m \"$@\"" backend
