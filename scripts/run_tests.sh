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
export IMA_ENDPOINT=http://localhost:1000
export DB_USER=user
export DB_PASSWORD=pass
export DB_PORT=3307
export FLASK_APP_HOST=0.0.0.0
export FLASK_APP_PORT=3008
export FLASK_DEBUG_MODE=True
export TM_URL=http://localhost:3009
export TG_CHAT_ID=-1231232
export TG_API_KEY=123
export ABI_FILEPATH=$TEST_ABI_FILEPATH

docker rm -f skale_schain_test1 skale_schain_test2 skale_schain_test3 || true
rm -rf $PWD/tests/dkg_test/sgx.*

bash scripts/run_sgx_simulator.sh
bash scripts/run_redis.sh

python tests/prepare_data.py

py.test tests/routes/ --ignore=tests/firewall --ignore=tests/rotation_test $@
export SGX_CERTIFICATES_FOLDER=$PWD/tests/skale-data/node_data/sgx_certs
mkdir -p $SGX_CERTIFICATES_FOLDER
rm -rf $SGX_CERTIFICATES_FOLDER/sgx.*
# todo: tmp, until skaled fix for single-node sChains:
py.test tests/rotation_test/ --ignore=tests/rotation_test/exit_test.py --ignore=tests/rotation_test/restart_test.py
find . -name \*.pyc -delete
scripts/run_firewall_test.sh
rm -r $SGX_CERTIFICATES_FOLDER
