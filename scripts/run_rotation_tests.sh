#!/usr/bin/env bash
set -e

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $DIR/helper.sh
source $DIR/../helper-scripts/helper.sh

: "${SGX_WALLET_TAG?Need to set SGX_WALLET_TAG}"

tests_cleanup
export_test_env

run_sgx_simulator $SGX_WALLET_TAG
bash scripts/run_redis.sh

python tests/prepare_data.py
py.test tests/rotation_test/

tests_cleanup