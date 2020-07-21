FROM python:buster



# RUN apt-get update && apt-get install -y software-properties-common && \
#     apt-get install -y python3.7 libpython3.7-dev python3.7-venv wget git python3.7-distutils && \
#     apt-get install -y libxslt-dev iptables

RUN apt-get update && apt-get install -y wget git libxslt-dev iptables

# RUN wget https://bootstrap.pypa.io/get-pip.py && \
#     python3.7 get-pip.py && \
#     ln -s /usr/bin/python3.7 /usr/local/bin/python3

RUN mkdir /usr/src/admin
WORKDIR /usr/src/admin

COPY requirements.txt ./
COPY requirements-dev.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir -r requirements-dev.txt

COPY . .

ENV PYTHONPATH="/usr/src/admin"
ENV COLUMNS=80
# CMD ["celery", "-A", "core.tg_bot", "worker", "--loglevel=info"]
