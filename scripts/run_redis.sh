set -e

docker rm -f redis || true
export DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
docker run -v $DIR/../tests/redis-conf:/config:Z --network=host --name=redis -d redis:6.0-alpine
