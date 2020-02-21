#!/usr/bin/env bash

# set -e

docker rm -f sgx_simulator
docker run -d -p 1026-1028:1026-1028 --name sgx_simulator skalenetwork/sgxwalletsim:latest -s -y -a
