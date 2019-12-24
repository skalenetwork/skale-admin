docker rm -f skale_schain_test && docker volume rm test
rm tests/skale-data/node_data/node_config.json

export SKALE_DIR_HOST=$PWD/tests/skale-data
export RUNNING_ON_HOST=True
export ENV=dev

py.test tests/
