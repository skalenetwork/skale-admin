#!/usr/bin/env bash

export ENDPOINT=http://127.0.0.1:8545
export MANAGER_TAG=1.12.0-develop.23
export IMA_TAG=2.3.0-beta.3

export FAIR_TAG=0.0.1-develop.50
export ETH_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 # anvil key 0 - testing key
export RUN_ANVIL=true

export SGX_WALLET_TAG=e548b375cae741af8fd11db54d6925c27a947af9

export SKALED_TAG=4.1.0-develop.24-mirage

export SKALE_DIR_HOST=$PWD/tests/skale-data
export SKALE_LIB_PATH=$PWD/tests/skale-data/lib
export RUNNING_ON_HOST=True
export PYTHONPATH=${PYTHONPATH}:.
export ENV=dev
export SGX_CERTIFICATES_FOLDER=$PWD/tests/skale-data/node_data/sgx_certs
export SGX_SERVER_URL=https://localhost:1026
export ENDPOINT=${ENDPOINT}
export DB_USER=user
export DB_PASSWORD=pass
export DB_PORT=3307
export FLASK_APP_HOST=0.0.0.0
export FLASK_APP_PORT=3008
export FLASK_DEBUG_MODE=True
export REDIS_URI="redis://@127.0.0.1:6379"
export TG_CHAT_ID=-1231232
export TG_API_KEY=123
export ENV_TYPE=devnet
export ENV=test
export ALLOWED_TS_DIFF=9000000
export SCHAIN_STOP_TIMEOUT=1

export MANAGER_CONTRACTS=$(bash $PWD/helper-scripts/helper.sh manager_address) || true
export IMA_CONTRACTS=$(bash $PWD/helper-scripts/helper.sh ima_address) || true
export FAIR_CONTRACTS=$(bash $PWD/helper-scripts/helper.sh fair_address) || true

export DEFAULT_GAS_PRICE_WEI=1000000000
