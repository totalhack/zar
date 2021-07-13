#! /usr/bin/env sh

# Exit in case of error
set -e

awslogs get zar ALL --start='5m' -w | grep -v "/api/v1/ok"
