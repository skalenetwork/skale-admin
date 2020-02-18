docker rm -f skale_schain_test && docker volume rm test
rm tests/skale-data/node_data/node_config.json

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_DIR=$(dirname $DIR)

export SKALE_DIR_HOST=$PWD/tests/skale-data
export RUNNING_ON_HOST=True
export PYTHONPATH=${PYTHONPATH}:.
export ENV=dev

python $PROJECT_DIR/tests/prepare_data.py

py.test $PROJECT_DIR/tests/ --ignore=tests/firewall
find . -name \*.pyc -delete
$PROJECT_DIR/scripts/run_firewall_test.sh
