FROM ubuntu:18.04

RUN apt-get update && apt-get install -y software-properties-common && \
    apt-get install -y libpython3.6-dev python3.6-venv wget gcc build-essential git \
    libboost-all-dev cmake libgmp3-dev libssl-dev pkg-config libxml2-dev libxslt-dev automake libtool libffi6

RUN wget https://deb.nodesource.com/setup_10.x && bash setup_10.x
RUN apt-get install -y nodejs

RUN wget https://bootstrap.pypa.io/get-pip.py && \
    python3.6 get-pip.py && \
    ln -s /usr/bin/python3.6 /usr/local/bin/python3

RUN mkdir /usr/src/admin
WORKDIR /usr/src/admin

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH="/usr/src/admin"
CMD [ "python3", "app.py" ]