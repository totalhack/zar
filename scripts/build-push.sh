#! /usr/bin/env sh

# Exit in case of error
set -e

TAG=${TAG-latest} \
sh ./scripts/build.sh

docker-compose -f docker-compose.yml push backend
