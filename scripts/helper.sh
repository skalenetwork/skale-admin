#!/usr/bin/env bash

tests_cleanup () {
    rm -r tests/skale-data/lib || true
    rm tests/skale-data/node_data/node_config.json || true
    find . -name \*.pyc -delete || true
}

sgx_cleanup () {
    if docker ps -a --format "table {{.Names}}" | grep -q "^sgx-simulator$"; then
        docker rm -f sgx-simulator
    fi

    echo SGX CERTS FOLDER $SGX_CERTIFICATES_FOLDER

    if ls $SGX_CERTIFICATES_FOLDER >/dev/null 2>&1; then
        rm -rf $SGX_CERTIFICATES_FOLDER/
    fi
    mkdir -p $SGX_CERTIFICATES_FOLDER
}
