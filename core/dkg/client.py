#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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

import logging
import os
from abc import ABC, abstractmethod

from eth_utils.hexadecimal import remove_0x_prefix
from sgx import SgxClient
from sgx.sgx_rpc_handler import SgxServerError

from core.dkg.broadcast_filter import BaseFilter
from core.dkg.structures import DKGStep
from core.dkg.utils import (
    convert_g2_array_to_hex,
    convert_g2_points_to_array,
    convert_hex_to_g2_array,
    convert_key_share_to_str,
    convert_str_to_key_share,
    generate_chain_bls_key_name,
    generate_chain_poly_name,
    to_verify,
)
from tools.constants import SGX_CERTIFICATES_FOLDER
from tools.helper import no_hyphens
from tools.resources import get_statsd_client
from tools.sgx_utils import sgx_unreachable_retry

logger = logging.getLogger(__name__)

ALRIGHT_GAS_LIMIT = 1000000


class BaseDKGClient(ABC):
    """
    Abstract base class for DKG clients.
    """

    def __init__(
        self,
        node_id_dkg,
        node_id_contract,
        skale,
        t,
        n,
        public_keys,
        node_ids_dkg,
        node_ids_contract,
        eth_key_name,
        rotation_id,
        chain_name,
        step,
    ):
        self.node_id_contract = node_id_contract
        self.node_id_dkg = node_id_dkg
        self.skale = skale
        self.t = t
        self.n = n
        self.sgx = SgxClient(
            os.environ['SGX_SERVER_URL'], n=n, t=t, path_to_cert=str(SGX_CERTIFICATES_FOLDER)
        )
        self.chain_name = chain_name
        self.eth_key_name = eth_key_name
        self.rotation_id = rotation_id
        self.incoming_verification_vector = ['0' for _ in range(n)]
        self.incoming_secret_key_contribution = ['0' for _ in range(n)]
        self.public_keys = public_keys
        self.node_ids_dkg = node_ids_dkg
        self.node_ids_contract = node_ids_contract
        self.statsd_client = get_statsd_client()
        self.group_index = self.skale.web3.keccak(text=self.chain_name)
        group_index_str = str(int(remove_0x_prefix(skale.web3.to_hex(self.group_index)), 16))
        self.poly_name = generate_chain_poly_name(group_index_str, self.node_id_dkg, rotation_id)
        self.bls_name = generate_chain_bls_key_name(group_index_str, self.node_id_dkg, rotation_id)
        self._last_completed_step = step  # last step

    @property
    def last_completed_step(self) -> DKGStep:
        return self._last_completed_step

    @last_completed_step.setter
    def last_completed_step(self, step: DKGStep):
        self.statsd_client.gauge(
            f'admin.schains.dkg.last_completed_step.{no_hyphens(self.chain_name)}', step.value
        )
        self._last_completed_step = step

    def store_broadcasted_data(self, data, from_node):
        self.incoming_secret_key_contribution[from_node] = data[1][
            192 * self.node_id_dkg : 192  # noqa
            * (self.node_id_dkg + 1)
        ]
        if from_node == self.node_id_dkg:
            self.incoming_verification_vector[from_node] = convert_hex_to_g2_array(data[0])
            self.sent_secret_key_contribution = convert_key_share_to_str(data[1], self.n)
        else:
            self.incoming_verification_vector[from_node] = data[0]

    @sgx_unreachable_retry
    def generate_polynomial(self, poly_name):
        self.poly_name = poly_name
        return self.sgx.generate_dkg_poly(poly_name)

    @sgx_unreachable_retry
    def verification_vector(self):
        verification_vector = self.sgx.get_verification_vector(self.poly_name)
        self.incoming_verification_vector[self.node_id_dkg] = verification_vector
        return convert_g2_points_to_array(verification_vector)

    @sgx_unreachable_retry
    def secret_key_contribution(self):
        self.sent_secret_key_contribution = self.sgx.get_secret_key_contribution_v2(
            self.poly_name, self.public_keys
        )
        self.incoming_secret_key_contribution[self.node_id_dkg] = self.sent_secret_key_contribution[
            self.node_id_dkg * 192 : (self.node_id_dkg + 1)  # noqa
            * 192
        ]
        return convert_str_to_key_share(self.sent_secret_key_contribution, self.n)

    @sgx_unreachable_retry
    def verification(self, from_node):
        return self.sgx.verify_secret_share_v2(
            self.incoming_verification_vector[from_node],
            self.eth_key_name,
            to_verify(self.incoming_secret_key_contribution[from_node]),
            self.node_id_dkg,
        )

    @sgx_unreachable_retry
    def is_bls_key_generated(self):
        try:
            self.sgx.get_bls_public_key(self.bls_name)
        except SgxServerError as err:
            if 'Data with this name does not exist' in err.args[0]:
                logger.info(f'No bls key with name {self.bls_name}, {err}')
                return False
            raise
        return True

    @sgx_unreachable_retry
    def fetch_bls_public_key(self):
        self.public_key = self.sgx.get_bls_public_key(self.bls_name)

    @sgx_unreachable_retry
    def get_bls_public_keys(self):
        self.incoming_verification_vector[self.node_id_dkg] = convert_g2_array_to_hex(
            self.incoming_verification_vector[self.node_id_dkg]
        )
        return self.sgx.calculate_all_bls_public_keys(self.incoming_verification_vector)

    def alright(self):
        if not self.is_alright_possible():
            return

        self._send_alright_transaction()
        self.last_completed_step = DKGStep.ALRIGHT

    @abstractmethod
    def is_node_broadcasted(self) -> bool:
        """
        Abstract method to check if the node has broadcasted its data.
        Should be implemented in subclasses.
        """
        pass

    @abstractmethod
    def _send_broadcast_transaction(self):
        """
        Sends the broadcast txn to the blockchain.
        This method should be implemented in subclasses.
        """

    @abstractmethod
    def _send_alright_transaction(self):
        """
        Sends the alright txn to the blockchain.
        This method should be implemented in subclasses.
        """

    @abstractmethod
    def get_broadcast_filter(self) -> BaseFilter:
        """
        Abstract method to get the broadcast filter.
        Should be implemented in subclasses.
        """
        pass

    @abstractmethod
    def is_everyone_broadcasted(self) -> bool:
        """
        Abstract method to check if everyone has broadcasted their data.
        Should be implemented in subclasses.
        """
        pass

    @abstractmethod
    def get_common_bls_public_key(self) -> list[str]:
        """
        Abstract method to get the common BLS public key.
        Should be implemented in subclasses.
        """
        pass

    @abstractmethod
    def is_broadcast_possible(self) -> bool:
        """
        Abstract method to check if broadcasting is possible.
        Should be implemented in subclasses.
        """
        pass

    @abstractmethod
    def is_alright_possible(self) -> bool:
        """
        Abstract method to check if sending an alright note is possible.
        Should be implemented in subclasses.
        """
        pass
