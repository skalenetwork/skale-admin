#!/bin/bash

export $(cat .env | xargs)

source $VIRTUAL_ENV/bin/activate
PARDIR=$(dirname $(pwd))
PYTHONPATH="${PARDIR}"
export FLASK_SECRET_KEY=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 13 ; echo '')


PYTHONPATH=$PYTHONPATH FLASK_ENV=development RUN_MODE=admin SKALE_DIR_HOST="$HOME"/.skale python ../$1.py

