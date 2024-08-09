#!/usr/bin/env bash

export_test_env () {
    export SKALE_DIR_HOST=$PWD/tests/skale-data
    export SKALE_LIB_PATH=$PWD/tests/skale-data/lib
    export RUNNING_ON_HOST=True
    export PYTHONPATH=${PYTHONPATH}:.
    export ENV=dev
    export SGX_CERTIFICATES_FOLDER=$PWD/tests/skale-data/node_data/sgx_certs
    export SGX_SERVER_URL=https://localhost:1026
    export ENDPOINT=http://localhost:8545
    export DB_USER=user
    export DB_PASSWORD=pass
    export DB_PORT=3307
    export FLASK_APP_HOST=0.0.0.0
    export FLASK_APP_PORT=3008
    export FLASK_DEBUG_MODE=True
    export TG_CHAT_ID=-1231232
    export TG_API_KEY=123
    export REDIS_URI="redis://@127.0.0.1:6381"
    export ENV_TYPE=devnet
    export ENV=test
    export ALLOWED_TS_DIFF=9000000
    export SCHAIN_STOP_TIMEOUT=1
    export ABI_FILEPATH=${ABI_FILEPATH="$PWD/helper-scripts/contracts_data/manager.json"}
    export IMA_ABI_FILEPATH=${IMA_ABI_FILEPATH}
    export DEFAULT_GAS_PRICE_WEI=1000000000

    cp $PWD/helper-scripts/contracts_data/ima.json $SKALE_DIR_HOST/contracts_info
}


tests_cleanup () {
    export_test_env
    docker rm -f skale_schain_test && docker volume rm test || true
    sudo rm -r tests/skale-data/lib || true
    rm tests/skale-data/node_data/node_config.json || true
    docker rm -f sgx-simulator || true
    docker rm -f skale_schain_test1 skale_schain_test2 skale_schain_test3 || true
    find . -name \*.pyc -delete || true
    mkdir -p $SGX_CERTIFICATES_FOLDER || true
    rm -rf $SGX_CERTIFICATES_FOLDER/sgx.* || true
}
