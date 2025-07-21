#!/usr/bin/env bash
set -ea

: "${SKALED_TAG?Need to set SKALED_TAG}"

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
if [ ! -d "$DIR/../tests/schain-data/.artifacts" ]; then
  mkdir -p "$DIR/../tests/schain-data/.artifacts"
fi

ulimit -n 65535

docker run -d \
  --name skaled \
  --network host \
  -v "$DIR/../tests/schain-data/.artifacts/skaled-datadir":"/skaled/datadir" \
  -v "$DIR/../tests/schain-data/fair-conf":"/skaled/config" \
  --ulimit nofile=65535:65535 \
  skalenetwork/schain:${SKALED_TAG} \
  --config config/skaled-config.json \
  --http-port 1234 \
  --ws-port 1233 \
  -v 4 \
  --web3-trace \
  --enable-debug-behavior-apis \
  --ipcpath ./datadir
