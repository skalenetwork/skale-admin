FROM python:3.14.10-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv

WORKDIR /usr/src/admin

COPY pyproject.toml ./

RUN uv pip install --system --no-cache -r pyproject.toml

FROM python:3.14.10-slim-trixie

RUN apt-get update && \
    apt-get install -y --no-install-recommends nftables python3-nftables && \
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
