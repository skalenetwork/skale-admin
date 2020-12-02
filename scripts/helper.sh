#!/usr/bin/env bash

export_test_env () {
    export SKALE_DIR_HOST=$PWD/tests/skale-data
    export RUNNING_ON_HOST=True
    export PYTHONPATH=${PYTHONPATH}:.
    export ENV=dev
    export SGX_CERTIFICATES_FOLDER=$PWD/tests/skale-data/node_data/sgx_certs
    export SGX_SERVER_URL=https://localhost:1026
    export ENDPOINT=http://localhost:8545
    export IMA_ENDPOINT=http://localhost:1000
    export DB_USER=user
    export DB_PASSWORD=pass
    export DB_PORT=3307
    export FLASK_APP_HOST=0.0.0.0
    export FLASK_APP_PORT=3008
    export FLASK_DEBUG_MODE=True
    export TM_URL=http://localhost:3009
    export TG_CHAT_ID=-1231232
    export TG_API_KEY=123
}


tests_cleanup () {
    export_test_env
    docker rm -f skale_schain_test && docker volume rm test
    rm tests/skale-data/node_data/node_config.json
    docker rm -f skale_schain_test1 skale_schain_test2 skale_schain_test3 || true
    find . -name \*.pyc -delete
    mkdir -p $SGX_CERTIFICATES_FOLDER
    rm -rf $SGX_CERTIFICATES_FOLDER/sgx.*
}
