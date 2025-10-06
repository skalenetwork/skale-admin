FROM python:3.13.7-slim-trixie

RUN apt-get update && apt-get install -y wget git libxslt-dev kmod nftables python3-nftables

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN mkdir /usr/src/admin
WORKDIR /usr/src/admin

COPY pyproject.toml ./

RUN pip3 install --no-cache-dir .

COPY . .

ENV PYTHONPATH="/usr/src/admin:/usr/lib/python3/dist-packages/"

ENV COLUMNS=80
