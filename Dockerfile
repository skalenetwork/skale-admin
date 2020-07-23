FROM python:buster

RUN apt-get update && apt-get install -y wget git libxslt-dev iptables

RUN mkdir /usr/src/admin
WORKDIR /usr/src/admin

COPY requirements.txt ./
COPY requirements-dev.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt && \
    pip3 install --no-cache-dir -r requirements-dev.txt

COPY . .

ENV PYTHONPATH="/usr/src/admin"
ENV COLUMNS=80
