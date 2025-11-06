FROM python:3.13.8-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /usr/src/admin

COPY pyproject.toml ./

RUN uv pip install --prerelease=allow --system --no-cache .

FROM python:3.13.8-slim-trixie

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget kmod nftables git python3-nftables && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/admin

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

ENV PYTHONPATH="/usr/src/admin:/usr/lib/python3/dist-packages/"
ENV COLUMNS=80
