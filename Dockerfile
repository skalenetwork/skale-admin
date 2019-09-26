FROM ubuntu:16.04

RUN apt-get update && apt-get install -y software-properties-common
RUN add-apt-repository -y ppa:jonathonf/python-3.6 && \
    apt-get update && \
    apt-get install -y python3.6 libpython3.6-dev python3.6-venv wget gcc libboost-python1.58.0 build-essential git \
    libboost-all-dev cmake libgmp3-dev libssl-dev libprocps4-dev pkg-config libxml2-dev libxslt-dev automake libtool libffi6

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

RUN cd frontend && npm i && npm run build

CMD [ "python3", "app.py" ]
