import logging
from dataclasses import dataclass

from skale import Skale

from tools.helper import get_containers_data
from web.models.schain import SChainRecord


logger = logging.getLogger(__name__)


@dataclass
class SchainData:
    name: str
    schain_id: str
    mainnet_owner: str
    part_of_node: int
    dkg_status: int
    is_deleted: bool
    first_run: bool
    repair_mode: bool

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'id': self.schain_id,
            'mainnet_owner': self.mainnet_owner,
            'part_of_node': self.part_of_node,
            'dkg_status': self.dkg_status,
            'is_deleted': self.is_deleted,
            'first_run': self.first_run,
            'repair_mode': self.repair_mode
        }


def get_schain_info_by_name(skale: Skale, schain_name: str) -> SchainData:
    sid = skale.schains.name_to_id(schain_name)
    contracts_info = skale.schains.get(sid)

    if SChainRecord.added(schain_name):
        record = SChainRecord.get_by_name(schain_name)
    else:
        logger.error('Schain record not exits')
        return None

    return SchainData(
        schain_name,
        sid,
        contracts_info['mainnetOwner'],
        contracts_info['partOfNode'],
        record.dkg_status,
        record.is_deleted,
        record.first_run,
        record.repair_mode
    )


def get_skaled_version() -> str:
    return get_containers_data()['schain']['version']
