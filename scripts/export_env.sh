#!/usr/bin/env bash

export ENDPOINT=http://127.0.0.1:8545
export MANAGER_TAG=1.12.0-develop.23
export IMA_TAG=2.3.0-beta.3
export FAIR_TAG=0.0.1-develop.50
export SGX_WALLET_TAG=e548b375cae741af8fd11db54d6925c27a947af9
export SKALED_TAG=4.1.0-develop.24-mirage

export ETH_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 # anvil key 0 - testing key
export RUN_ANVIL=true

export SKALE_VOLUME_PATH=$PWD/tests/skale-data
export SGX_CERTIFICATES_FOLDER=$SKALE_VOLUME_PATH/node_data/sgx_certs
export PYTHONPATH=${PYTHONPATH}:.

export CONTRACTS__MANAGER=$(bash $PWD/helper-scripts/helper.sh manager_address) || true
export CONTRACTS__IMA=$(bash $PWD/helper-scripts/helper.sh ima_address) || true
export CONTRACTS__FAIR=$(bash $PWD/helper-scripts/helper.sh fair_address) || true

if [ $SKALE_NETWORK_TYPE == "fair" ]; then
  export ENDPOINT=http://127.0.0.1:1234
  export RUN_ANVIL=false
fi