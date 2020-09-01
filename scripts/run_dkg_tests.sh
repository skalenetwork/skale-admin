set -e

: "${SCHAIN_TYPE?Need to set SCHAIN_TYPE - test2, test4 or tiny}"

export SKALE_DIR_HOST=$PWD/tests/skale-data
export RUNNING_ON_HOST=True
export PYTHONPATH=${PYTHONPATH}:.
export ENV=dev
export SGX_CERTIFICATES_FOLDER=$PWD/dkg/sgx_certs/
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
export TEST_ABI_FILEPATH=$PWD/test_abi.json

echo $SGX_CERTIFICATES_FOLDER
rm -r $SGX_CERTIFICATES_FOLDER || true
mkdir $SGX_CERTIFICATES_FOLDER
python dkg/test.py
