#! /usr/bin/env sh

# Exit in case of error
set -e

sh ./scripts/config.sh | node ./scripts/repair_compose.mjs | \
DOCKER_CONTEXT=${DOCKER_CONTEXT?Variable not set} \
docker stack deploy -c - --with-registry-auth "${STACK_NAME?Variable not set}"
