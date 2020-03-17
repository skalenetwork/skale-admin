docker rm -f skale_schain_test && docker volume rm test
rm tests/skale-data/node_data/node_config.json

set -e
export SKALE_DIR_HOST=$PWD/tests/skale-data
export RUNNING_ON_HOST=True
export PYTHONPATH=${PYTHONPATH}:.
export ENV=dev

scripts/run_firewall_test.sh
find . -name \*.pyc -delete
py.test tests/ --ignore=tests/firewall --ignore=tests/node_test.py --ignore=tests/test_skale_filter.py
