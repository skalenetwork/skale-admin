docker rm -f skale_schain_test && docker volume rm test
rm tests/skale-data/node_data/node_config.json

set -e
export SKALE_DIR_HOST=$PWD/tests/skale-data
export RUNNING_ON_HOST=True
export PYTHONPATH=${PYTHONPATH}:.
export ENV=dev
export $(cat tests/test-env | xargs)

py.test tests/ --ignore=tests/firewall
find . -name \*.pyc -delete
scripts/run_firewall_test.sh
