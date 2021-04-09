#!/usr/bin/env bash

set -e

: "${ETH_PRIVATE_KEY?Need to set ETH_PRIVATE_KEY}"
: "${MANAGER_TAG?Need to set MANAGER_TAG}"

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
export DOCKER_NETWORK_ENDPOINT=http://ganache:8545

docker rm -f ganache || true
docker network create testnet || true

rm $DIR/contracts_data/skale-manager-* || true

docker run -d --network testnet -p 8545:8545 -p 8546:8546 \
    --name ganache trufflesuite/ganache-cli:v6.8.1-beta.0 \
    --account="0x${ETH_PRIVATE_KEY},100000000000000000000000000" -l 10000000 -b 0.1

docker pull skalenetwork/skale-manager:$MANAGER_TAG
docker run \
    -v $DIR/contracts_data:/usr/src/manager/data \
    --network testnet \
    -e ENDPOINT=$DOCKER_NETWORK_ENDPOINT \
    -e PRIVATE_KEY=$ETH_PRIVATE_KEY \
    skalenetwork/skale-manager:$MANAGER_TAG \
    npx hardhat run migrations/deploy.ts --network custom

cp $DIR/contracts_data/skale-manager-* $DIR/../tests/test_abi.json
