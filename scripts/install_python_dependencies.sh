#!/usr/bin/env bash
set -ea

pip install -r requirements.txt
pip install -r requirements-dev.txt
find . -name "*.pyc" -exec rm -f {} \;
