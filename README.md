# SKALE Admin

[![Build Status](https://travis-ci.com/skalenetwork/skale-admin.svg?token=tLesVRTSHvWZxoyqXdoA&branch=develop)](https://travis-ci.com/skalenetwork/skale-admin)
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