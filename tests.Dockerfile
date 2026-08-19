FROM admin:base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nftables python3-nftables && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

RUN uv pip install --prerelease=allow --no-cache ".[test,dev]"
