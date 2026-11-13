FROM admin:base

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

COPY pyproject.toml ./

RUN uv pip install --system --no-cache -r pyproject.toml --extra test --extra dev
