#!/usr/bin/env bash
set -ea

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $DIR/helper.sh
source $DIR/../helper-scripts/helper.sh

: "${SGX_WALLET_TAG?Need to set SGX_WALLET_TAG}"

tests_cleanup

export_test_env

bash scripts/run_redis.sh

uv run pytest --cov=. tests --ignore=tests/dkg_test --ignore=tests/firewall --ignore=tests/fair $@
tests_cleanup
sgx_cleanup
