#!/usr/bin/env bash

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip uninstall pycrypto -y
pip uninstall pycryptodome -y
pip install pycryptodome
find . -name "*.pyc" -exec rm -f {} \;