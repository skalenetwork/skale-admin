#!/usr/bin/env bash
set -ea

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

docker rm -f test-firewall || true
docker build -t admin:base .
docker build -f tests.Dockerfile -t test-firewall .
docker run -v "$DIR/../tests/skale-data/node_data":"/skale_node_data" \
    -v "$DIR/../tests/skale-data":"/skale_vol" \
    -e SGX_SERVER_URL="https://127.0.0.1:1026" \
    -e ENDPOINT="http://127.0.0.1:8545" \
    -e DB_USER="test" \
    -e DB_PASSWORD="pass" \
    -e DB_ROOT_PASSWORD="root-test-pass" \
    -e DB_PORT=3307 \
    -e SKALE_DIR_HOST=/skale_dir_host \
    --cap-add=NET_ADMIN --cap-add=NET_RAW \
    --name test-firewall test-firewall pytest --cov core.schains.firewall tests/firewall/ $@
