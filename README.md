# SKALE Admin

![Test](https://github.com/skalenetwork/skale-admin/workflows/Test/badge.svg)
![Build and publish](https://github.com/skalenetwork/skale-admin/workflows/Build%20and%20publish/badge.svg)
[![Discord](https://img.shields.io/discord/534485763354787851.svg)](https://discord.gg/vvUtWJB)

This repo contains source code for 3 core SKALE Node containers:

* `skale_admin` - worker that manages sChains creation and node rotation
* `skale_api` - webserver that provides node API
* `celery` - distributed task queue

## Local CLI authentication

State-changing API routes and `GET /api/v1/node/signature` require an
`Authorization: Bearer <token>` header. This applies to the SKALE and FAIR API
applications, including passive FAIR setup. Read-only routes remain accessible
without credentials, including the two FAIR staking query routes that use POST.

Node CLI generates a random per-node credential before starting services. It is
stored on the host at `~<node-user>/.skale/auth/admin-api.token` and read by
the API at `${SKALE_VOLUME_PATH}/auth/admin-api.token` (normally
`/skale_vol/auth/admin-api.token`). The API's existing `.skale` mount exposes this
folder. The CLI gives the `auth` directory mode `0700` and the token mode `0600`,
both owned by the configured node user. The API container must run as root or the
file owner's UID.

Containers mounting only `node_data` do not receive the credential. Some node
services mount all of `.skale`, which also exposes `auth`; to isolate the token
from these services, replace their broad mounts with the specific directories
they need. Moving the token alone does not restrict those containers.

Authentication runs before node initialization waits, database connections, and
wallet setup. Missing or invalid client credentials return HTTP 401. A missing,
unreadable, malformed, symlinked, or incorrectly permissioned server token returns
HTTP 503 for protected routes; it never disables authentication. Errors retain
the normal `status`/`payload` JSON format.

Upgrade Node CLI first, then use it to update/start the node services. Existing
tokens in `auth` are preserved. CLI backups exclude the entire `auth` directory,
including temporary token files, so restoring onto a fresh host generates a new
credential. Both sides read the file for each request,
allowing an operator to rotate it by atomically replacing it with a newly
generated 64-character lowercase hex token, preserving ownership and mode 0600.

If using the earlier `node_data/admin-api.token` layout, the updated CLI creates
a fresh token in `auth` before starting services. The API does not accept the old
token from `node_data` or fall back to that location.

Keep the API bound to loopback (`127.0.0.1:3007`). This authenticates the local
operator's credential, not the CLI executable: root, the node user, and privileged
containers able to read the shared volume can also use it with other clients.

To protect another endpoint, place `@cli_only` from `web.auth` immediately below
its route decorator and above resource initialization decorators such as
`@g_skale`. Both API entry points must register `init_cli_auth(app)` before their
resource initialization hooks.

## Development

### Dependencies

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install all dependencies:

```bash
uv sync --prerelease=allow --all-extras
```

### Linting and type checking

#### Check linting/formatting issues

```bash
uv run ruff check
```

#### Check type issues

```bash
uv run mypy .
```

#### Auto-fix ruff issues (linting + formatting)

```bash
uv run ruff check --fix
```

# Format code with ruff

```bash
uv run ruff format
```

In file `.git/hooks/pre-commit` add:

```shell
#!/bin/sh
uv run ruff check
```

### Run tests locally

1. Run local ganache, download and deploy SKALE Manager contracts to it

   ```bash
   ETH_PRIVATE_KEY=[..] MANAGER_BRANCH=[..] bash ./scripts/deploy_manager.sh
   ```

   * `ETH_PRIVATE_KEY` - it could be any valid Ethereum private key (without `0x` prefix!)
   * `MANAGER_BRANCH` - tag of the SKALE Manager image to use (`$MANAGER_BRANCH-latest` will be used)
   * `SGX_WALLET_TAG` - tag of the SGX simulator to use (optional, `latest` will be used by default)

   List of the available SM tags: <https://hub.docker.com/r/skalenetwork/skale-manager/tags>\
   List of the available SGX tags: <https://hub.docker.com/r/skalenetwork/sgxwallet_sim/tags>

2. Run SGX wallet simulator and all tests after it

```bash
ETH_PRIVATE_KEY=[...] SCHAIN_TYPE=[...] bash ./scripts/run_tests.sh
```

* `ETH_PRIVATE_KEY` - it could be any valid Ethereum private key (without `0x` prefix!)
* `SCHAIN_TYPE` - type of the chain for the DKG test (could be `test2` - 2 nodes, `test4` - 4 nodes, `tiny` - 16 nodes)

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
