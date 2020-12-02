#!/usr/bin/env bash

bash scripts/run_sgx_simulator.sh
python tests/prepare_data.py

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip uninstall pycrypto -y
pip uninstall pycryptodome -y
pip install pycryptodome
find . -name "*.pyc" -exec rm -f {} \;