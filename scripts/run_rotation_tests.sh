#!/usr/bin/env bash
set -e

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $DIR/helper.sh
source $DIR/../helper-scripts/helper.sh

tests_cleanup
export_test_env

py.test tests/rotation_test/

tests_cleanup
