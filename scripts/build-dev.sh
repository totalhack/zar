#! /usr/bin/env sh

# Exit in case of error
set -e

DOCKER_IMAGE_BACKEND=${DOCKER_IMAGE_BACKEND?Variable not set} \
TAG=${TAG-latest} \
docker-compose \
-f docker-compose.override.yml \
build --no-cache
