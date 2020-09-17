FROM admin:base

ENV RUNNING_ON_HOST=''
ENV SKALE_DIR_HOST=/skale_dir_host

VOLUME tests/skale-data/node_data /skale_node_data

RUN pip3 install --no-cache-dir -r requirements-dev.txt
