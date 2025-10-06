#!/usr/bin/env bash
set -ea

uv sync --prerelease=allow --all-extras
find . -name "*.pyc" -exec rm -f {} \;
