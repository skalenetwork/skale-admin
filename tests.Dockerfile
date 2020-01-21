FROM ubuntu:18.04

RUN apt-get update && apt-get install -y software-properties-common && \
    apt-get install -y python3.7 libpython3.7-dev python3.7-venv wget git python3.7-distutils libxslt-dev iptables python3-pip sudo

RUN ln -s /usr/bin/python3.7 /usr/local/bin/python3

RUN mkdir /app
WORKDIR /app

COPY requirements.txt ./
COPY requirements-dev.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir -r requirements-dev.txt

COPY . .

ENV PYTHONPATH="/app"
