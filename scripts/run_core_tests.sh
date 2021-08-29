#!/usr/bin/env bash
set -e

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $DIR/helper.sh
source $DIR/../helper-scripts/helper.sh

: "${SGX_WALLET_TAG?Need to set SGX_WALLET_TAG}"
: "${SCHAIN_TYPE?Need to set SCHAIN_TYPE - test2, test4 or tiny}"

tests_cleanup
export_test_env

run_sgx_simulator $SGX_WALLET_TAG
bash scripts/run_redis.sh

# python tests/prepare_data.py
py.test tests/  --ignore=tests/firewall --ignore=tests/rotation_test $@
tests_cleanup
# scripts/run_firewall_test.sh
# tests_cleanup
