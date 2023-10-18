import os
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.schains.firewall.types import IpRange
from core.schains.config.directory import schain_config_dir
from tools.helper import read_json, write_json


@dataclass
class ExternalState:
    chain_id: int
    ranges: field(default_factory=list)
    ima_linked: bool = False

    def to_dict(self):
        return {
            'chain_id': self.chain_id,
            'ima_linked': self.ima_linked,
            'ranges': list(map(list, self.ranges))
        }


class ExternalConfig:
    FILENAME = 'external.json'

    _lock = threading.Lock()

    def __init__(self, name: str) -> None:
        self.path = os.path.join(schain_config_dir(name), ExternalConfig.FILENAME)

    @property
    def ima_linked(self) -> bool:
        return self.read().get('ima_linked', True)

    @property
    def chain_id(self) -> Optional[int]:
        return self.read().get('chain_id', None)

    @property
    def ranges(self) -> List[IpRange]:
        plain_ranges = self.read().get('ranges', [])
        return list(sorted(map(lambda r: IpRange(*r), plain_ranges)))

    def get(self) -> Optional[ExternalState]:
        plain = self.read()
        if plain:
            return ExternalState(
                chain_id=plain['chain_id'],
                ima_linked=plain['ima_linked'],
                ranges=list(sorted(map(lambda r: IpRange(*r), plain['ranges'])))

            )
        return None

    def read(self) -> Dict:
        data = {}
        with ExternalConfig._lock:
            if os.path.isfile(self.path):
                data = read_json(self.path)
        return data

    def write(self, content: Dict) -> None:
        with ExternalConfig._lock:
            write_json(self.path, content)

    def update(self, ex_state: ExternalState) -> None:
        self.write(ex_state.to_dict())

    def synced(self, ex_state: ExternalState) -> bool:
        return self.get() == ex_state
