#! /usr/bin/env sh

# Exit in case of error
set -e

DOMAIN=${DOMAIN?Variable not set} \
STACK_NAME=${STACK_NAME?Variable not set} \
TAG=${TAG-latest} \
DOCKER_IMAGE_BACKEND=${DOCKER_IMAGE_BACKEND?Variable not set} \
docker-compose \
-f docker-compose.yml \
config