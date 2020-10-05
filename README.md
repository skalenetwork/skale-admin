# SKALE Admin

![Test](https://github.com/skalenetwork/skale-admin/workflows/Test/badge.svg)
![Build and publish](https://github.com/skalenetwork/skale-admin/workflows/Build%20and%20publish/badge.svg)
[![Discord](https://img.shields.io/discord/534485763354787851.svg)](https://discord.gg/vvUtWJB)

SKALE Admin is the container that manages all operations on the SKALE node.

## API Reference

1.  [SSL](#schains-ssl-api)

### sChains SSL API

#### Status

> Login required

    [GET] /api/ssl/status

##### Response

Success:

> Status: `200`

```json
{
    "res": 1,
    "data": {
        "status": 1,
        "expiration_date": "2020-02-19T09:59:16",
        "issued_to": "*.abc.com"
    }
}
```

No certs:

> Status: `200`

```json
{
    "res": 1,
    "data": {
        "status": 0
    }
}
```

#### Upload

> Login required

    [POST] /api/ssl/upload

Form content:

```json
{
    "force": "True/False",
    "ssl_key": "[KEY_FILE]",
    "ssl_cert": "[CERT_FILE]",
}
```

##### Response

OK:

> Status: `200`

```json
{
    "res": 1,
    "data": null
}
```

Certificates are already uploaded/Wrong form content:

> Status: `400`

```json
{
    "res": 0,
    "error_msg": "[ERR_MESSAGE_STRING]"
}
```

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
