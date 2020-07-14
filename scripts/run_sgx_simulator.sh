#!/usr/bin/env bash

set -e

SGX_WALLET_TAG=${SGX_WALLET_TAG:-develop-latest}
SGX_WALLET_IMAGE_NAME=skalenetwork/sgxwallet_sim:$SGX_WALLET_TAG
SGX_WALLET_CONTAINER_NAME=sgx_simulator

docker rm -f $SGX_WALLET_CONTAINER_NAME || true
docker pull $SGX_WALLET_IMAGE_NAME
docker run -d -p 1026-1028:1026-1028 --name $SGX_WALLET_CONTAINER_NAME $SGX_WALLET_IMAGE_NAME -s -y -a
