#! /usr/bin/env bash

# Exit in case of error
set -e

eval `egrep -v '^#' .env | grep -v BACKEND_CORS | xargs` \
docker compose convert -f docker-compose.yml
