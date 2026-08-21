#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import functools
import logging
import time

from eth_keys.datatypes import Signature
from eth_keys.exceptions import BadSignature
from eth_utils import ValidationError
from sgx import SgxClient
from sgx.http import SgxUnreachableError
from sgx.utils import SgxError
from skale_core.settings import FairSettings, SkaleSettings, get_settings
from zmq.error import ZMQBaseError

from tools.constants import SGX_CERTIFICATES_FOLDER
from tools.str_formatters import arguments_list_string

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 14
TIMEOUTS = [2**p for p in range(RETRY_ATTEMPTS)]

# Constant 32 byte hash used to probe the sgx signing path
SIGNING_CHECK_HASH = bytes.fromhex('11' * 32)

# Offset added to the recovery id by eth_account when signing without a chain id
SIGNATURE_V_OFFSET = 27

SGX_CHECK_ERRORS = (
    SgxError,
    ZMQBaseError,
    OSError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
)
SGX_SIGNING_ERRORS = (*SGX_CHECK_ERRORS, BadSignature, ValidationError)


class EmptySgxUrlError(Exception):
    """Raised when admin couldn't establish connection with SGX server"""


def sgx_unreachable_retry(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result, error = None, None
        for i, timeout in enumerate(TIMEOUTS):
            try:
                result = func(*args, **kwargs)
            except SgxUnreachableError as err:
                logger.info(f'Sgx server is unreachable during try {i}')
                error = err
                time.sleep(timeout)
            else:
                error = None
                break
        if error is not None:
            raise error
        return result

    return wrapper


@sgx_unreachable_retry
def generate_sgx_key(config):
    logger.info('Generating sgx key...')
    if not config.sgx_key_name:
        st = get_settings((SkaleSettings, FairSettings))
        sgx = SgxClient(str(st.sgx_url), SGX_CERTIFICATES_FOLDER)
        key_info = sgx.generate_key()
        logger.info(
            arguments_list_string(
                {'Name hash': key_info.name, 'Address': key_info.address}, 'Generated new SGX key'
            )
        )
        config.sgx_key_name = key_info.name


def get_sgx_key_address(sgx: SgxClient, key_name: str) -> str | None:
    try:
        return sgx.get_account(key_name).address
    except SGX_CHECK_ERRORS as err:
        logger.error(f'Cannot read sgx key {key_name}: {err}')
        return None


def check_sgx_signing(sgx: SgxClient, key_name: str, address: str) -> bool:
    try:
        signed_hash = sgx.sign_hash(SIGNING_CHECK_HASH, key_name, None)
        signature = Signature(
            vrs=(signed_hash.v - SIGNATURE_V_OFFSET, signed_hash.r, signed_hash.s)
        )
        public_key = signature.recover_public_key_from_msg_hash(SIGNING_CHECK_HASH)
        signer = public_key.to_checksum_address()
    except SGX_SIGNING_ERRORS as err:
        logger.error(f'Cannot sign with sgx key {key_name}: {err}')
        return False
    if signer != address:
        logger.error(f'Sgx key {key_name} signed as {signer}, expected {address}')
        return False
    return True
