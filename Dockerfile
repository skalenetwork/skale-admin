FROM python:3.14.7-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /usr/src/admin

COPY pyproject.toml ./

RUN uv pip install --prerelease=allow --system --no-cache .

FROM python:3.14.7-slim-trixie

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget kmod nftables git python3-nftables && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/admin

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# dist-packages is built against the distribution interpreter, so it is added
# through a .pth file that appends it to the end of sys.path, where it cannot
# shadow the pinned packages.
RUN echo /usr/lib/python3/dist-packages > /usr/local/lib/python3.14/site-packages/dist-packages.pth

COPY . .

ENV PYTHONPATH="/usr/src/admin"
ENV COLUMNS=80
