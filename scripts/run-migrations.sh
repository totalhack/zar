#! /usr/bin/env bash

# Exit in case of error
set -e

docker-compose run --rm --entrypoint "alembic -c /app/alembic.ini upgrade head" backend
