set -e

docker rm -f test-firewall || true

docker build -t admin:base .
docker build -f tests.Dockerfile -t test-firewall .
docker run --cap-add=NET_ADMIN --cap-add=NET_RAW --name test-firewall test-firewall pytest tests/firewall/
