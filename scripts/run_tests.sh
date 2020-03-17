docker rm -f skale_schain_test && docker volume rm test
rm tests/skale-data/node_data/node_config.json

set -e

: "${SCHAIN_TYPE?Need to set SCHAIN_TYPE - test2, test4 or tiny}"

export SKALE_DIR_HOST=$PWD/tests/skale-data
export RUNNING_ON_HOST=True
export PYTHONPATH=${PYTHONPATH}:.
export ENV=dev
export SGX_CERTIFICATES_FOLDER=$PWD/tests/dkg_test/
export SGX_SERVER_URL=https://localhost:1026
export ENDPOINT=http://localhost:8545
export DB_USER=user
export DB_PASSWORD=pass
export DB_PORT=3307
export IMA_ENDPOINT=http://localhost:1000

docker rm -f skale_schain_test1 skale_schain_test2 skale_schain_test3 || true
rm -rf $PWD/tests/dkg_test/sgx.*

bash scripts/run_sgx_simulator.sh

python tests/prepare_data.py

py.test tests/ --ignore=tests/firewall
find . -name \*.pyc -delete
scripts/run_firewall_test.sh
