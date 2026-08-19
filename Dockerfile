FROM ubuntu:24.04 AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Ubuntu 24.04 ships python3.12, so the interpreter is provided by uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python

WORKDIR /usr/src/admin

COPY pyproject.toml ./

RUN uv venv --python 3.13.15 /opt/venv && \
    uv pip install --prerelease=allow --python /opt/venv/bin/python --no-cache .

FROM ubuntu:24.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates wget kmod nftables git python3-nftables && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/admin

COPY --from=builder /opt/python /opt/python
COPY --from=builder /opt/venv /opt/venv

# The nftables bindings are only available as an apt package. Registering
# dist-packages through a .pth file appends it to the end of sys.path, so the
# distribution packages never shadow the pinned ones in the virtualenv.
RUN echo /usr/lib/python3/dist-packages > /opt/venv/lib/python3.13/site-packages/dist-packages.pth

COPY . .

ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="/opt/venv/bin:${PATH}"
ENV PYTHONPATH="/usr/src/admin"
ENV COLUMNS=80
