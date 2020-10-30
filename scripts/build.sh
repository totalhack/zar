#! /usr/bin/env sh

# Exit in case of error
set -e

TAG=${TAG-latest} \
DOCKER_IMAGE_BACKEND="totalhack/zar-backend" \
docker-compose \
-f docker-compose.yml \
build

