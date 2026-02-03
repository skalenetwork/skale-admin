#!/usr/bin/env bash
set -ea

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

docker rm -f test-firewall || true
docker build -t admin:base .
docker build -f tests.Dockerfile -t test-firewall .
docker run -v "$DIR/../tests/skale-data/node_data":"/skale_node_data" \
    -v "$DIR/../tests/skale-data":"/skale_vol" \
    --cap-add=NET_ADMIN --cap-add=NET_RAW \
    --name test-firewall test-firewall pytest --cov core.firewall tests/firewall/ $@
