#!/usr/bin/env bash
set -ea

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $DIR/helper.sh
source $DIR/../helper-scripts/helper.sh

: "${SGX_WALLET_TAG?Need to set SGX_WALLET_TAG}"

sgx_cleanup
#run_sgx_simulator $SGX_WALLET_TAG
SGX_WALLET_IMAGE_NAME=ghcr.io/skalenetwork/sgxwallet_sim:$SGX_WALLET_TAG
docker run -d -p 1026-1031:1026-1031 --name sgx-simulator --entrypoint /bin/bash $SGX_WALLET_IMAGE_NAME -c "source /opt/intel/sgxsdk/environment && cd /usr/src/sdk && ./sgxwallet -s -y"
bash scripts/run_redis.sh
