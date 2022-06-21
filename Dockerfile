FROM python:3.9-bullseye

RUN apt-get update && apt-get install -y
    wget \
    git \
    libxslt-dev \
    iptables \
    nftables \
    python3-nftables \
    kmod \
    swig4.0
RUN ln -s /usr/bin/swig4.0 /usr/bin/swig

RUN mkdir /usr/src/admin
WORKDIR /usr/src/admin

COPY requirements.txt ./
COPY requirements-dev.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt 

RUN pip3 uninstall pycrypto -y
RUN pip3 uninstall pycryptodome -y
RUN pip3 install pycryptodome

COPY . .

RUN update-alternatives --set iptables /usr/sbin/iptables-legacy && \
    update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy 

ENV PYTHONPATH="/usr/lib/python3/dist-packages:/usr/src/admin"
ENV COLUMNS=80
