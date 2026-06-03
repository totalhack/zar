#!/usr/bin/env bash

set -e
set -x

export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"

pytest app/tests "${@}"
