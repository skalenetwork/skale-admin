FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y wget git libxslt-dev iptables kmod swig

RUN mkdir /usr/src/admin
WORKDIR /usr/src/admin

COPY requirements.txt ./
COPY requirements-dev.txt ./

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN update-alternatives --set iptables /usr/sbin/iptables-legacy && \
    update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy 

ENV PYTHONPATH="/usr/src/admin"
ENV COLUMNS=80
