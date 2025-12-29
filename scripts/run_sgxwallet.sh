#!/usr/bin/env bash
set -ea

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $DIR/helper.sh
source $DIR/../helper-scripts/helper.sh

: "${SGX_WALLET_TAG?Need to set SGX_WALLET_TAG}"

sgx_cleanup
#run_sgx_simulator $SGX_WALLET_TAG
docker run -d -p 1026-1031:1026-1031 --name $SGX_WALLET_CONTAINER_NAME --entrypoint /bin/bash $SGX_WALLET_IMAGE_NAME -c "source /opt/intel/sgxsdk/environment && cd /usr/src/sdk && ./sgxwallet -y -n"
bash scripts/run_redis.sh
