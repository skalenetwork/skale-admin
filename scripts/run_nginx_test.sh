#!/usr/bin/env bash
set -ea

export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

docker pull nginx:1.29.5
cd "$DIR/.."
uv run pytest --cov core.nginx tests/test_nginx.py tests/nginx_proxy_test.py $@
