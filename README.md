# SKALE Admin

![Test](https://github.com/skalenetwork/skale-admin/workflows/Test/badge.svg)
![Build and publish](https://github.com/skalenetwork/skale-admin/workflows/Build%20and%20publish/badge.svg)
[![Discord](https://img.shields.io/discord/534485763354787851.svg)](https://discord.gg/vvUtWJB)

This repo contains source code for 3 core SKALE Node containers:

- `skale_admin` - worker that manages sChains creation and node rotation
- `skale_api` - webserver that provides node API
- `celery` - distributed task queue

## API reference

SKALE API reference could be found in the docs repo: [SKALE Node API](http://docs.skalenetwork.com/).

## Development

### Run tests locally

1) Run local ganache, download and deploy SKALE Manager contracts to it

```bash
ETH_PRIVATE_KEY=[..] MANAGER_BRANCH=[..] bash ./scripts/deploy_manager.sh
```

- `ETH_PRIVATE_KEY` - it could be any valid Ethereum private key (without `0x` prefix!)
- `MANAGER_BRANCH` - tag of the SKALE Manager image to use (`$MANAGER_BRANCH-latest` will be used)
- `SGX_WALLET_TAG` - tag of the SGX simulator to use (optional, `latest` will be used by default)

List of the available SM tags: https://hub.docker.com/r/skalenetwork/skale-manager/tags  
List of the available SGX tags: https://hub.docker.com/r/skalenetwork/sgxwalletsim/tags

2) Run SGX wallet simulator and all tests after it

```bash
ETH_PRIVATE_KEY=[...] SCHAIN_TYPE=[...] bash ./scripts/run_tests.sh
```

- `ETH_PRIVATE_KEY` - it could be any valid Ethereum private key (without `0x` prefix!)
- `SCHAIN_TYPE` - type of the chain for the DKG test (could be `test2` - 2 nodes, `test4` - 4 nodes, `tiny` - 16 nodes)

Test build:

```bash
export BRANCH=$(git branch | grep -oP "^\*\s+\K\S+$")
export VERSION=$(bash scripts/calculate_version.sh)
bash scripts/build.sh
```

## License

[![License](https://img.shields.io/github/license/skalenetwork/skale-admin.svg)](LICENSE)

All contributions to SKALE Admin are made under the [GNU Affero General Public License v3](https://www.gnu.org/licenses/agpl-3.0.en.html). See [LICENSE](LICENSE).

Copyright (C) 2019-Present SKALE Labs.
