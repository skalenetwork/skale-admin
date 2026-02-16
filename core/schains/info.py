import logging
from dataclasses import dataclass

from skale import SkaleManager
from skale.types.schain import SchainName
from skale.utils.helper import schain_name_to_hash
from web3 import Web3

from tools.helper import containers_info
from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)


@dataclass
class SchainData:
    name: str
    schain_id: bytes
    mainnet_owner: str
    part_of_node: int
    dkg_status: int
    is_deleted: bool
    first_run: bool
    repair_ts: int

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'id': Web3.to_hex(self.schain_id),
            'mainnet_owner': self.mainnet_owner,
            'part_of_node': self.part_of_node,
            'dkg_status': self.dkg_status,
            'is_deleted': self.is_deleted,
            'first_run': self.first_run,
            'repair_ts': self.repair_ts,
        }


def get_schain_info_by_name(skale: SkaleManager, schain_name: SchainName) -> SchainData:
    sid = schain_name_to_hash(schain_name)
    contracts_info = skale.schains.get(sid)

    if SChainRecord.added(schain_name):
        record = SChainRecord.get_by_name(schain_name)
    else:
        logger.error('Schain record not exits')
        return None

    return SchainData(
        schain_name,
        sid,
        contracts_info.mainnet_owner,
        contracts_info.part_of_node,
        record.dkg_status,
        record.is_deleted,
        record.first_run,
        int(record.repair_date.timestamp()),
    )


def get_skaled_version() -> str:
    return containers_info()['skaled']['version']
