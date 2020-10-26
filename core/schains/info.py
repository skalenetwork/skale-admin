import logging
from dataclasses import dataclass

from skale import Skale

from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)


@dataclass
class SChainInfo:
    name: str
    schain_id: str
    owner: str
    part_of_node: int
    dkg_status: int
    is_deleted: bool
    first_run: bool
    repair_mode: bool

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'id': self.schain_id,
            'owner': self.owner,
            'part_of_node': self.part_of_node,
            'dkg_status': self.dkg_status,
            'is_deleted': self.is_deleted,
            'first_run': self.first_run,
            'repair_mode': self.repair_mode
        }


def get_schain_info_by_name(skale: Skale, schain_name: str) -> SChainInfo:
    sid = skale.schains.name_to_id(schain_name)
    contracts_info = skale.schains.get(sid)

    if SChainRecord.added(schain_name):
        record = SChainRecord.get_by_name(schain_name)
    else:
        logger.error('Schain record not exits')
        return None

    return SChainInfo(
        schain_name,
        sid,
        contracts_info['owner'],
        contracts_info['partOfNode'],
        record.dkg_status,
        record.is_deleted,
        record.first_run,
        record.repair_mode
    )
