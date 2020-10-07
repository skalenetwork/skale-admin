set -e

export $(grep -v '^#' .env | xargs)

mkdir -p $SKALE_BASE_DIR || true
mkdir -p $SGX_CERTIFICATES_FOLDER || true

export SKALE_DIR_HOST=$PWD/tests/skale-data
export RUNNING_ON_HOST=True
export IMA_ENDPOINT=http://localhost:1000
export DB_USER=user
export DB_PASSWORD=pass
export DB_PORT=3307
export FLASK_APP_HOST=0.0.0.0
export FLASK_APP_PORT=3008
export FLASK_DEBUG_MODE=True

python test.py
