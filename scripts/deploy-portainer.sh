#! /usr/bin/env sh

# Exit in case of error
set -e

DOCKER_CONTEXT=${DOCKER_CONTEXT?Variable not set} \
docker stack deploy -c portainer-agent-stack.yml portainer

