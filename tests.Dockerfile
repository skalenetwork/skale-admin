FROM admin:base

RUN apt update && apt install -y nftables python3-nftables

RUN pip3 install -r requirements-dev.txt

ENV PYTHONPATH=${PYTHONPATH}:/usr/lib/python3/dist-packages/
