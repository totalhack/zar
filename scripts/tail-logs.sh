#! /usr/bin/env sh

# Exit in case of error
set -e

start_time="${1:-5m}"
awslogs get zar ALL --start="$start_time" -w -S -G -f '[w1!="*/api/v1/ok*"]'
