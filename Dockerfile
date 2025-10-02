FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y wget git libxslt-dev kmod swig nftables python3-nftables

RUN mkdir /usr/src/admin
WORKDIR /usr/src/admin

COPY requirements.txt ./
COPY requirements-dev.txt ./

RUN pip3 install -r requirements.txt

COPY . .

ENV PYTHONPATH="/usr/src/admin":/usr/lib/python3/dist-packages/

ENV COLUMNS=80
