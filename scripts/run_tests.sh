docker rm -f skale_schain_test && docker volume rm test
rm tests/skale-data/node_data/node_config.json

set -e

export SKALE_DIR_HOST=$PWD/tests/skale-data
export RUNNING_ON_HOST=True
export PYTHONPATH=${PYTHONPATH}:.
export ENV=dev
export SGX_CERTIFICATES_FOLDER=$PWD/tests/dkg_test/
export SGX_SERVER_URL=http://localhost:1026
export ENDPOINT=http://localhost:8545

bash scripts/run_sgx_simulator.sh

python tests/prepare_data.py

py.test tests/ --ignore=tests/firewall
find . -name \*.pyc -delete
scripts/run_firewall_test.sh
