set -e

docker rm -f test-firewall || true
DIR=$PWD
docker build -t admin:base .
docker build -f tests.Dockerfile -t test-firewall .
docker run -v "$DIR/tests/skale-data/node_data":"/skale_node_data":Z \
    -v "$DIR/tests/skale-data":"/skale_vol":Z \
    -e REDIS_URL="redis://127.0.0.1:6379" \
    -e SGX_SERVER_URL="https://127.0.0.1:1026" \
    -e ENDPOINT="http://127.0.0.1:8545" \
    -e IMA_ENDPOINT="http://127.0.01:1000" \
    -e DB_USER="test" \
    -e DB_PASSWORD="pass" \
    -e DB_ROOT_PASSWORD="root-test-pass" \
    -e DB_PORT=3307 \
    -e SKALE_DIR_HOST=/skale_dir_host \
    --cap-add=NET_ADMIN --cap-add=NET_RAW \
    --name test-firewall test-firewall pytest tests/firewall/
